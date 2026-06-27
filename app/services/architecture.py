import torch
import torch.nn as nn
import timm

class ImageBranch(nn.Module):
    """
    EfficientNet-B3 branch for images — Spatial Output
    """
    def __init__(self, embedding_dim=256, pretrained=False):
        super().__init__()

        self.backbone = timm.create_model(
            'efficientnet_b3',
            pretrained=pretrained,
            num_classes=0,
            global_pool=''
        )

        self.pool = nn.AdaptiveAvgPool2d((7, 7))
        feat_dim = self.backbone.num_features  # 1536

        self.projection = nn.Sequential(
            nn.Conv2d(feat_dim, 512, kernel_size=1),
            nn.BatchNorm2d(512),
            nn.GELU(),
            nn.Dropout2d(0.3),  
            nn.Conv2d(512, embedding_dim, kernel_size=1),
            nn.BatchNorm2d(embedding_dim)
        )

    def forward(self, x):
        features = self.backbone(x)         # [B, 1536, H', W']
        features = self.pool(features)      # [B, 1536, 7, 7]
        proj_features = self.projection(features) # [B, 256, 7, 7]
        return proj_features.flatten(2).transpose(1, 2)  # [B, 49, 256]

class MLPBranch(nn.Module):
    """
    MLP branch for metadata — SYNCHRONIZED with training code
    """
    def __init__(self, num_features=10, embedding_dim=64):
        super().__init__()

        self.mlp = nn.Sequential(
            # Layer 1
            nn.Linear(num_features, 128),
            nn.LayerNorm(128),   
            nn.GELU(),
            nn.Dropout(0.3),     

            # Layer 2
            nn.Linear(128, 64),
            nn.LayerNorm(64),    
            nn.GELU(),
            nn.Dropout(0.2),     

            # Layer 3
            nn.Linear(64, embedding_dim),
            nn.LayerNorm(embedding_dim),  
        )

    def forward(self, x):
        return self.mlp(x)

class GatedCrossAttentionFusion(nn.Module):
    """
    GatedCrossAttentionFusion — SYNCHRONIZED with training code
    """
    def __init__(self, img_dim=256, meta_dim=64, num_classes=6, num_heads=4):
        super().__init__()
        d_model = 256

        self.meta_proj = nn.Sequential(
            nn.Linear(meta_dim, d_model),
            nn.LayerNorm(d_model)
        )
        self.img_norm = nn.LayerNorm(d_model)

        self.pos_embedding = nn.Parameter(torch.zeros(1, 49, d_model))
        nn.init.trunc_normal_(self.pos_embedding, std=0.02)

        self.attention = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=0.1,
            batch_first=True
        )

        self.img_pool_proj = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.LayerNorm(d_model)
        )

        self.gate = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
            nn.Sigmoid()
        )

        self.classifier = nn.Sequential(
            nn.Linear(d_model, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.4),    

            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.3),    

            nn.Linear(128, num_classes)
        )

    def forward(self, img_patches, meta_emb):
        meta_token  = self.meta_proj(meta_emb).unsqueeze(1)           
        img_patches = self.img_norm(img_patches) + self.pos_embedding 

        attended, _ = self.attention(
            query=meta_token,
            key=img_patches,
            value=img_patches
        )                                                              

        img_global = self.img_pool_proj(img_patches.mean(dim=1, keepdim=True))  

        g = self.gate(torch.cat([attended, img_global], dim=-1))      
        fused = g * attended + (1.0 - g) * img_global                 

        logits = self.classifier((meta_token + fused).squeeze(1))     
        return logits, g

class MultimodalModel_v4(nn.Module):
    """
    MultimodalModel v4.2 — SYNCHRONIZED with training code
    """
    def __init__(self, num_metadata_features=3, num_classes=6,
                 img_embedding_dim=256, meta_embedding_dim=64,
                 pretrained=False):
        super().__init__()

        self.image_branch = ImageBranch(
            embedding_dim=img_embedding_dim,
            pretrained=pretrained
        )
        self.mlp_branch = MLPBranch(
            num_features=num_metadata_features,
            embedding_dim=meta_embedding_dim
        )
        self.fusion = GatedCrossAttentionFusion(
            img_dim=img_embedding_dim,
            meta_dim=meta_embedding_dim,
            num_classes=num_classes
        )

    def forward(self, image, metadata):
        img_patches = self.image_branch(image)
        meta_emb = self.mlp_branch(metadata)
        logits, gate = self.fusion(img_patches, meta_emb)
        return logits, gate
