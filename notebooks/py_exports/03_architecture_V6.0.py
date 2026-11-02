# ═══ NOTEBOOK: 03_architecture_V6.0.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 03: Architecture V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | meta_mask support in MLPBranch & MedAssistModel, Swin Transformer support, gamma=2.5, label_smoothing=0.05 |
# | V5.0 | 7 meta features, auxiliary head, GatedCrossAttentionFusion with positional embeddings |
# | V4.2 | 11 meta features, basic cross-attention |
# 
# ## Changes vs V5.0
# - `meta_mask` parameter in MLPBranch.forward() and MedAssistModel.forward()
# - Swin Transformer output format handling in ImageBranch
# - `import math` added at top level
# - `class_alpha` removed (unused variable)


# ────────────────────────────────────────────────────────────
# ## CELL 1 — Imports & Load Config


# ── Cell 3 ───────────────────────────────────────
import os, json, math
import torch
import torch.nn as nn
import torch.nn.functional as F
import timm
import numpy as np

from google.colab import drive
drive.mount('/content/drive')

BASE_PATH = '/content/drive/MyDrive/MedAssist_AI'
PROCESSED_PATH = os.path.join(BASE_PATH, 'data', 'processed')
MODELS_PATH = os.path.join(BASE_PATH, 'models')
os.makedirs(MODELS_PATH, exist_ok=True)

with open(os.path.join(PROCESSED_PATH, 'preprocessing_config.json')) as f:
    config = json.load(f)

assert config['version'] == 'V6.0'
NUM_CLASSES = config['num_classes']
NUM_META = config['num_meta_features']
CLASS_NAMES = config['class_names']
IMG_SIZE = config['img_size']

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'✅ Config loaded: {NUM_META} features, {NUM_CLASSES} classes, img={IMG_SIZE}')
print(f'✅ Device: {device}')


# ────────────────────────────────────────────────────────────
# ## CELL 2 — GeM Pooling & Image Branch (EfficientNet-B3)


# ── Cell 5 ───────────────────────────────────────
class GeM(nn.Module):
    """Generalized Mean Pooling — أفضل من AvgPool في medical imaging."""
    def __init__(self, p: float = 3.0, eps: float = 1e-6):
        super().__init__()
        self.p   = nn.Parameter(torch.tensor(p, dtype=torch.float32))
        self.eps = eps
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.avg_pool2d(
            x.clamp(min=self.eps).pow(self.p),
            (x.size(-2), x.size(-1))
        ).pow(1.0 / self.p)
class ImageBranch(nn.Module):
    def __init__(self, num_classes=6, embed_dim=256, backbone_name='efficientnet_b3'):
        super().__init__()
        self.backbone_name = backbone_name
        self.backbone = timm.create_model(backbone_name, pretrained=True,
                                          num_classes=0, global_pool='')
        backbone_dim = self.backbone.num_features

        # Projection: 1536 -> 512 -> embed_dim
        self.projection = nn.Sequential(
            nn.Conv2d(backbone_dim, 512, 1),
            nn.BatchNorm2d(512),
            nn.GELU(),
            nn.Conv2d(512, embed_dim, 1),
            nn.BatchNorm2d(embed_dim),
        )

        # Auxiliary classification head (image-only)
        self.auxiliary_head = nn.Sequential(
            GeM(p=3.0),          # ✅ إصلاح: GeM بدل AdaptiveAvgPool2d(1)
            nn.Flatten(),
            nn.Linear(backbone_dim, 256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )

        self.pool = nn.AdaptiveAvgPool2d(7)  # -> 7x7
        self.embed_dim = embed_dim

    def forward(self, x):
        features = self.backbone(x)          # (B, C, H, W) or (B, L, C)

        # Handle Swin Transformer output format from timm
        if 'swin' in self.backbone_name:
            if features.dim() == 3: # (B, L, C) -> (B, C, H, W)
                B, L, C = features.shape
                H = W = int(math.sqrt(L))
                features = features.transpose(1, 2).view(B, C, H, W)
            elif features.dim() == 4 and features.shape[1] == features.shape[2]: # (B, H, W, C)
                features = features.permute(0, 3, 1, 2)

        aux_logits = self.auxiliary_head(features)  # (B, 6)

        pooled = self.pool(features)          # (B, 1536, 7, 7)
        projected = self.projection(pooled)   # (B, 256, 7, 7)
        B, C, H, W = projected.shape
        patches = projected.view(B, C, H*W).permute(0, 2, 1)  # (B, 49, 256)

        return patches, aux_logits, features

# Test
_ib = ImageBranch().to(device)
_x = torch.randn(2, 3, IMG_SIZE, IMG_SIZE).to(device)
with torch.no_grad():
    _p, _a, _f = _ib(_x)
print(f'✅ ImageBranch: patches={_p.shape}, aux_logits={_a.shape}, features={_f.shape}')
del _ib, _x, _p, _a, _f
torch.cuda.empty_cache()


# ────────────────────────────────────────────────────────────
# ## CELL 3 — MLP Branch (Metadata + meta_mask)


# ── Cell 7 ───────────────────────────────────────
class MLPBranch(nn.Module):
    def __init__(self, num_features=7, embed_dim=64):
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

    def forward(self, x, meta_mask=None):
        if meta_mask is not None:
            x = x * meta_mask.float()
        return self.net(x)  # (B, 64)

# Test
_mlp = MLPBranch(NUM_META).to(device)
_m = torch.randn(2, NUM_META).to(device)
with torch.no_grad():
    _out = _mlp(_m)
print(f'✅ MLPBranch: input={_m.shape} -> output={_out.shape}')
del _mlp, _m, _out



# ────────────────────────────────────────────────────────────
# ## CELL 4 — Gated Cross-Attention Fusion


# ── Cell 9 ───────────────────────────────────────
class GatedCrossAttentionFusion(nn.Module):
    def __init__(self, img_embed_dim=256, meta_embed_dim=64, num_classes=6, num_heads=4):
        super().__init__()
        self.embed_dim = img_embed_dim

        # Project metadata to image embedding dim
        self.meta_proj = nn.Sequential(
            nn.Linear(meta_embed_dim, img_embed_dim),
            nn.LayerNorm(img_embed_dim),
        )

        # Image patch normalization
        self.img_norm = nn.LayerNorm(img_embed_dim)

        # Learnable positional embeddings for 49 patches
        self.pos_embed = nn.Parameter(torch.zeros(1, 49, img_embed_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        # Cross-attention: Q=metadata, K=V=image patches
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=img_embed_dim, num_heads=num_heads,
            dropout=0.1, batch_first=True
        )

        # Global image pooling projection
        self.img_global_pool_proj = nn.Sequential(
            nn.Linear(img_embed_dim, img_embed_dim),
            nn.LayerNorm(img_embed_dim),
        )

        # Gate: sigma(Linear([attended; global] -> embed_dim))
        self.gate = nn.Sequential(
            nn.Linear(img_embed_dim * 2, img_embed_dim),
            nn.Sigmoid()
        )

        # Final classifier: 256 -> 256 -> 128 -> num_classes
        self.classifier = nn.Sequential(
            nn.Linear(img_embed_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.55),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.45),
            nn.Linear(128, num_classes)
        )

    def forward(self, patches, meta_emb):
        # patches: (B, 49, 256), meta_emb: (B, 64)
        B = patches.size(0)

        # Project metadata -> (B, 1, 256)
        meta_q = self.meta_proj(meta_emb).unsqueeze(1)

        # Add positional embeddings to patches
        patches_norm = self.img_norm(patches + self.pos_embed)

        # Cross-attention: Q=meta, K=V=patches
        attended, _ = self.cross_attn(meta_q, patches_norm, patches_norm)
        attended = attended.squeeze(1)  # (B, 256)

        # Global image pooling
        img_global = patches.mean(dim=1)  # (B, 256)
        img_global = self.img_global_pool_proj(img_global)

        # Gating
        gate_input = torch.cat([attended, img_global], dim=-1)  # (B, 512)
        g = self.gate(gate_input)  # (B, 256)
        fused = g * attended + (1 - g) * img_global  # (B, 256)

        # Classify
        logits = self.classifier(fused)  # (B, 6)

        return logits, g.unsqueeze(1)  # gate shape: (B, 1, 256)

# Test
_fuse = GatedCrossAttentionFusion().to(device)
_p = torch.randn(2, 49, 256).to(device)
_me = torch.randn(2, 64).to(device)
with torch.no_grad():
    _logits, _gate = _fuse(_p, _me)
print(f'✅ Fusion: logits={_logits.shape}, gate={_gate.shape}')


# ────────────────────────────────────────────────────────────
# ## CELL 5 — Full MedAssistModel V6.0 (with meta_mask)


# ── Cell 11 ───────────────────────────────────────
del _fuse, _p, _me, _logits, _gate
class MedAssistModel(nn.Module):
    def __init__(self, num_meta=7, num_classes=6, img_embed_dim=256, meta_embed_dim=64, backbone_name='efficientnet_b3'):
        super().__init__()
        self.image_branch = ImageBranch(num_classes=num_classes, embed_dim=img_embed_dim, backbone_name=backbone_name)
        self.mlp_branch = MLPBranch(num_features=num_meta, embed_dim=meta_embed_dim)
        self.fusion = GatedCrossAttentionFusion(
            img_embed_dim=img_embed_dim,
            meta_embed_dim=meta_embed_dim,
            num_classes=num_classes,
            num_heads=4
        )

    def forward(self, images, metadata, meta_mask=None):
        # Image branch
        patches, aux_logits, _ = self.image_branch(images)
        # Metadata branch
        meta_emb = self.mlp_branch(metadata, meta_mask)
        # Fusion
        main_logits, gate = self.fusion(patches, meta_emb)
        # ALWAYS return all three
        return main_logits, aux_logits, gate

print('✅ MedAssistModel V6.0 defined')


# ────────────────────────────────────────────────────────────
# ## CELL 6 — WeightedFocalLoss (gamma=2.5, label_smoothing=0.05)


# ── Cell 13 ───────────────────────────────────────
class WeightedFocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0, label_smoothing=0.05):
        super().__init__()
        self.gamma = gamma
        self.label_smoothing = label_smoothing
        if alpha is not None:
            self.register_buffer('alpha', torch.tensor(alpha, dtype=torch.float32))
        else:
            self.alpha = None

    def forward(self, logits, targets):
        num_classes = logits.size(-1)
        log_probs = F.log_softmax(logits, dim=-1)
        probs = torch.exp(log_probs)

        pt = probs.gather(1, targets.unsqueeze(1)).squeeze(1)
        focal_weight = (1 - pt) ** self.gamma

        if self.label_smoothing > 0:
            smooth = self.label_smoothing / (num_classes - 1)
            log_pt = log_probs.gather(1, targets.unsqueeze(1)).squeeze(1)
            ce = -(1.0 - self.label_smoothing) * log_pt \
                 - smooth * log_probs.sum(dim=-1)
        else:
            ce = F.nll_loss(log_probs, targets, reduction='none')

        loss = focal_weight * ce

        if self.alpha is not None:
            alpha_t = self.alpha.gather(0, targets)
            loss = alpha_t * loss

        return loss.mean()
class_alpha = [1.0, 1.0, 3.0, 1.5, 4.0, 1.5]  # ACK, BCC, MEL, NEV, SCC, SEK
criterion = WeightedFocalLoss(
    alpha=None, gamma=2.0, label_smoothing=0.05).to(device)




# ────────────────────────────────────────────────────────────
# ## CELL 7 — Full Model Sanity Test


# ── Cell 15 ───────────────────────────────────────
print('🔬 Running full model sanity test...')
model = MedAssistModel(num_meta=NUM_META, num_classes=NUM_CLASSES).to(device)

# Count parameters
total = sum(p.numel() for p in model.parameters())
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'📊 Parameters: {total:,} total, {trainable:,} trainable')

# Forward pass test
B = 4
dummy_imgs = torch.randn(B, 3, IMG_SIZE, IMG_SIZE).to(device)
dummy_meta = torch.randn(B, NUM_META).to(device)

with torch.no_grad():
    main_logits, aux_logits, gate = model(dummy_imgs, dummy_meta)

print(f'\n✅ Forward pass successful!')
print(f'  main_logits: {main_logits.shape}  (B, {NUM_CLASSES})')
print(f'  aux_logits:  {aux_logits.shape}  (B, {NUM_CLASSES})')
print(f'  gate:        {gate.shape}  (B, 1, 256)')

# Loss test
class_weights = np.load(os.path.join(PROCESSED_PATH, 'class_weights.npy'))
loss_fn = WeightedFocalLoss(alpha=class_weights.tolist(), gamma=2.0, label_smoothing=0.0).to(device)
dummy_labels = torch.randint(0, NUM_CLASSES, (B,)).to(device)

main_loss = loss_fn(main_logits, dummy_labels)
aux_loss = loss_fn(aux_logits, dummy_labels)
total_loss = 0.7 * main_loss + 0.3 * aux_loss

print(f'\n✅ Loss computation:')
print(f'  main_loss:  {main_loss.item():.4f}')
print(f'  aux_loss:   {aux_loss.item():.4f}')
print(f'  total_loss: {total_loss.item():.4f} (0.7*main + 0.3*aux)')

# Gate statistics
print(f'\n📊 Gate stats: mean={gate.mean():.3f}, std={gate.std():.3f}')

# Cleanup
del model, dummy_imgs, dummy_meta, main_logits, aux_logits, gate
torch.cuda.empty_cache()
print('\n✅ All sanity tests passed!')



# ────────────────────────────────────────────────────────────
# ## CELL 8 — Save Model Config & Initial Weights


# ── Cell 17 ───────────────────────────────────────
# Save model config
model_config = {
    'version': 'V6.0',
    'architecture': 'CNN-ViT Ensemble Ready (EfficientNet/Swin) + GatedCrossAttentionFusion',
    'backbone': 'efficientnet_b3',
    'backbone_dim': 1536,
    'img_embed_dim': 256,
    'meta_embed_dim': 64,
    'num_meta_features': NUM_META,
    'num_classes': NUM_CLASSES,
    'num_patches': 49,
    'num_heads': 4,
    'mlp_layers': [128, 64, 64],
    'classifier_layers': [256, 128],
    'loss': 'WeightedFocalLoss',
    'loss_gamma': 2.0,
    'loss_label_smoothing': 0.05,
    'aux_weight': 0.3,
    'main_weight': 0.7,
    'img_size': IMG_SIZE
}

config_path = os.path.join(MODELS_PATH, 'model_config_v6.json')
with open(config_path, 'w') as f:
    json.dump(model_config, f, indent=2)
print(f'saved -> {config_path}')

# Save initial weights
model = MedAssistModel(num_meta=NUM_META, num_classes=NUM_CLASSES).to(device)
init_path = os.path.join(MODELS_PATH, 'model_init_v6.pth')
torch.save(model.state_dict(), init_path)
print(f'saved -> {init_path}')

del model
torch.cuda.empty_cache()
print('\n✅ Architecture V6.0 complete — ready for Notebook 04a')
