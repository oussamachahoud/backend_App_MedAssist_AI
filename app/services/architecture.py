"""
app/services/architecture.py
MedAssist AI V6.0 model architecture — exact match with training notebooks.

Classes:
    GeM                     — Generalized Mean Pooling
    ImageBranch             — EfficientNet-B3 / Swin backbone with auxiliary head
    MLPBranch               — Metadata MLP with meta_mask support
    GatedCrossAttentionFusion — Cross-attention fusion with learnable gate
    MedAssistModel          — Full multimodal model (CNN + MLP + Fusion)

V6.0 changes vs V4.x:
    - GeM pooling (p=3.0) in auxiliary head instead of AdaptiveAvgPool2d
    - meta_mask parameter in MLPBranch.forward() and MedAssistModel.forward()
    - Swin Transformer output format handling in ImageBranch
    - Classifier dropout rates: 0.55 / 0.45
    - Gate: Linear(512→256) + Sigmoid (no LayerNorm inside gate)
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


# ── Generalized Mean Pooling ──────────────────────────────────────────────────

class GeM(nn.Module):
    """
    Generalized Mean Pooling (GeM).
    Outperforms AvgPool for medical imaging tasks.
    p=3.0 is a learnable parameter, optimised during training.
    """

    def __init__(self, p: float = 3.0, eps: float = 1e-6):
        super().__init__()
        self.p = nn.Parameter(torch.tensor(p, dtype=torch.float32))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.avg_pool2d(
            x.clamp(min=self.eps).pow(self.p),
            (x.size(-2), x.size(-1)),
        ).pow(1.0 / self.p)


# ── Image Branch ──────────────────────────────────────────────────────────────

class ImageBranch(nn.Module):
    """
    CNN backbone branch for dermoscopy images.

    Architecture:
        backbone (EfficientNet-B3 or Swin)
        → auxiliary classification head   (GeM → FC → 6 logits)
        → 7×7 pooling + 1×1 convolutions  (→ 49 patch embeddings of dim 256)

    Supports both EfficientNet (4-D feature maps) and
    Swin Transformer (3-D / 4-D spatial output) via format detection.
    """

    def __init__(
        self,
        num_classes: int = 6,
        embed_dim: int = 256,
        backbone_name: str = "efficientnet_b3",
    ):
        super().__init__()
        self.backbone_name = backbone_name
        self.backbone = timm.create_model(
            backbone_name,
            pretrained=False,
            num_classes=0,
            global_pool="",
        )
        backbone_dim = self.backbone.num_features  # 1536 for EfficientNet-B3

        # Projection: backbone_dim → 512 → embed_dim  (1×1 convolutions)
        self.projection = nn.Sequential(
            nn.Conv2d(backbone_dim, 512, 1),
            nn.BatchNorm2d(512),
            nn.GELU(),
            nn.Conv2d(512, embed_dim, 1),
            nn.BatchNorm2d(embed_dim),
        )

        # Auxiliary image-only classification head
        self.auxiliary_head = nn.Sequential(
            GeM(p=3.0),           # (B, C, 1, 1)
            nn.Flatten(),         # (B, C)
            nn.Linear(backbone_dim, 256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

        self.pool = nn.AdaptiveAvgPool2d(7)  # → (B, C, 7, 7)
        self.embed_dim = embed_dim

    def forward(self, x: torch.Tensor):
        features = self.backbone(x)  # (B, C, H, W)  or  (B, L, C)  for Swin

        # --- Handle Swin Transformer output layouts ---
        if "swin" in self.backbone_name:
            if features.dim() == 3:          # (B, L, C) → (B, C, H, W)
                B, L, C = features.shape
                H = W = int(math.sqrt(L))
                features = features.transpose(1, 2).view(B, C, H, W)
            elif features.dim() == 4 and features.shape[1] == features.shape[2]:
                # (B, H, W, C) → (B, C, H, W)
                features = features.permute(0, 3, 1, 2)

        aux_logits = self.auxiliary_head(features)          # (B, num_classes)

        pooled    = self.pool(features)                     # (B, C, 7, 7)
        projected = self.projection(pooled)                 # (B, embed_dim, 7, 7)
        B, C, H, W = projected.shape
        patches = projected.view(B, C, H * W).permute(0, 2, 1)  # (B, 49, embed_dim)

        return patches, aux_logits, features


# ── MLP Branch ────────────────────────────────────────────────────────────────

class MLPBranch(nn.Module):
    """
    MLP branch for clinical metadata.

    Supports meta_mask: a binary tensor of shape (B, num_features) where 0
    marks missing / imputed features.  Missing features are zeroed-out BEFORE
    the first linear layer so the model learns to ignore them.
    """

    def __init__(self, num_features: int = 7, embed_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(num_features, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Dropout(0.35),
            nn.Linear(64, embed_dim),
        )

    def forward(self, x: torch.Tensor, meta_mask=None) -> torch.Tensor:
        if meta_mask is not None:
            x = x * meta_mask.float()
        return self.net(x)  # (B, embed_dim)


# ── Gated Cross-Attention Fusion ──────────────────────────────────────────────

class GatedCrossAttentionFusion(nn.Module):
    """
    Fuses image patch embeddings with metadata embedding via cross-attention.

    Query  = metadata token  (B, 1, img_embed_dim)
    Key/Val = image patches  (B, 49, img_embed_dim)

    A learnable gate blends the attended representation with a global
    average-pooled image representation before the final classifier.
    """

    def __init__(
        self,
        img_embed_dim: int = 256,
        meta_embed_dim: int = 64,
        num_classes: int = 6,
        num_heads: int = 4,
    ):
        super().__init__()
        self.embed_dim = img_embed_dim

        # Project metadata embedding → image embedding space
        self.meta_proj = nn.Sequential(
            nn.Linear(meta_embed_dim, img_embed_dim),
            nn.LayerNorm(img_embed_dim),
        )

        # Patch normalisation + learnable positional embeddings (49 patches)
        self.img_norm  = nn.LayerNorm(img_embed_dim)
        self.pos_embed = nn.Parameter(torch.zeros(1, 49, img_embed_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        # Cross-attention: Q=metadata, K=V=image patches
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=img_embed_dim,
            num_heads=num_heads,
            dropout=0.1,
            batch_first=True,
        )

        # Global image pool projection
        self.img_global_pool_proj = nn.Sequential(
            nn.Linear(img_embed_dim, img_embed_dim),
            nn.LayerNorm(img_embed_dim),
        )

        # Gate: σ(Linear([attended; global] → embed_dim))  — no LayerNorm
        self.gate = nn.Sequential(
            nn.Linear(img_embed_dim * 2, img_embed_dim),
            nn.Sigmoid(),
        )

        # Classifier: 256 → 256 → 128 → num_classes
        self.classifier = nn.Sequential(
            nn.Linear(img_embed_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.55),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.45),
            nn.Linear(128, num_classes),
        )

    def forward(self, patches: torch.Tensor, meta_emb: torch.Tensor):
        # patches: (B, 49, 256)  |  meta_emb: (B, 64)
        meta_q      = self.meta_proj(meta_emb).unsqueeze(1)          # (B, 1, 256)
        patches_norm = self.img_norm(patches + self.pos_embed)        # (B, 49, 256)

        attended, _ = self.cross_attn(meta_q, patches_norm, patches_norm)
        attended    = attended.squeeze(1)                             # (B, 256)

        img_global = patches.mean(dim=1)                              # (B, 256)
        img_global = self.img_global_pool_proj(img_global)

        g     = self.gate(torch.cat([attended, img_global], dim=-1))  # (B, 256)
        fused = g * attended + (1.0 - g) * img_global                 # (B, 256)

        logits = self.classifier(fused)                               # (B, num_classes)
        return logits, g.unsqueeze(1)                                 # gate: (B, 1, 256)


# ── Full Multimodal Model ─────────────────────────────────────────────────────

class MedAssistModel(nn.Module):
    """
    MedAssist AI V6.0 — multimodal skin lesion classifier.

    Inputs:
        images   : (B, 3, 256, 256)  — preprocessed dermoscopy images
        metadata : (B, 7)            — clinical feature vector
        meta_mask: (B, 7)  optional  — 1 where feature is available, 0 where imputed

    Outputs:
        main_logits : (B, 6)    — primary classifier logits
        aux_logits  : (B, 6)    — auxiliary image-only classifier logits
        gate        : (B, 1, 256) — cross-attention gate weights
    """

    def __init__(
        self,
        num_meta: int = 7,
        num_classes: int = 6,
        img_embed_dim: int = 256,
        meta_embed_dim: int = 64,
        backbone_name: str = "efficientnet_b3",
    ):
        super().__init__()
        self.image_branch = ImageBranch(
            num_classes=num_classes,
            embed_dim=img_embed_dim,
            backbone_name=backbone_name,
        )
        self.mlp_branch = MLPBranch(
            num_features=num_meta,
            embed_dim=meta_embed_dim,
        )
        self.fusion = GatedCrossAttentionFusion(
            img_embed_dim=img_embed_dim,
            meta_embed_dim=meta_embed_dim,
            num_classes=num_classes,
            num_heads=4,
        )

    def forward(self, images: torch.Tensor, metadata: torch.Tensor, meta_mask=None):
        patches, aux_logits, _ = self.image_branch(images)
        meta_emb               = self.mlp_branch(metadata, meta_mask)
        main_logits, gate      = self.fusion(patches, meta_emb)
        return main_logits, aux_logits, gate
