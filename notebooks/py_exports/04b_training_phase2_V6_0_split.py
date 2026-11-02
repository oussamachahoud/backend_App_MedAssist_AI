# ═══ NOTEBOOK: 04b_training_phase2_V6_0_split.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 04b: Training Phase 2 V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | Continues from phase1_state.json, img=256, meta_mask in all loops, SkinLesionDataset searches PAD+ISIC+MCR dirs, custom_update_bn() for multimodal SWA |
# | V5.0 | Lower LRs (backbone 5e-6, head 5e-5), SWA from epoch 15, per-class threshold optimization |
# | V4.2 | Single-phase training |
# 
# ## Purpose
# - Phase 2: 45 epochs at img=256 (fine-tuning)
# - Loads best Phase 1 checkpoint automatically
# - SWA (Stochastic Weight Averaging) starts at epoch 15
# - custom_update_bn() handles multimodal model BN update
# - Thresholds file always generated (prevents 05 crash)
# - Auto-resume from Phase 2 checkpoint on session reconnect


# ────────────────────────────────────────────────────────────
# ## CELL 0 — Environment Setup & Imports


# ── Cell 3 ───────────────────────────────────────
"""MedAssist AI - 04b Training Phase 2 V6.0 (Epochs 36-60) with SWA"""

from google.colab import drive
try:
    drive.mount('/content/drive')
except Exception:
    print('Drive already mounted.')

import subprocess, sys
for pkg in ['mlflow', 'timm', 'albumentations', 'transformers', 'scikit-learn']:
    try:
        __import__(pkg if pkg != 'scikit-learn' else 'sklearn')
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

import os, gc, csv, json, math, pickle, warnings, glob, time
import numpy as np, pandas as pd, cv2
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torch.cuda.amp import autocast, GradScaler
from torch.optim.swa_utils import AveragedModel, SWALR, update_bn
import timm
import albumentations as A
from albumentations.pytorch import ToTensorV2
from sklearn.metrics import f1_score, classification_report
from transformers import get_cosine_schedule_with_warmup
import mlflow
from tqdm.auto import tqdm

warnings.filterwarnings('ignore')
torch.backends.cudnn.benchmark = True

VERSION = 'V6.0'
BASE_PATH = '/content/drive/MyDrive/MedAssist_AI'
DATASET_PATH = os.path.join(BASE_PATH, 'dataset')
PROCESSED_PATH = os.path.join(BASE_PATH, 'data', 'processed')
MODELS_PATH = os.path.join(BASE_PATH, 'models')
RESULTS_PATH = os.path.join(BASE_PATH, 'results')
MLFLOW_DIR = os.path.join(RESULTS_PATH, 'mlruns')
for p in [MODELS_PATH, RESULTS_PATH, MLFLOW_DIR]:
    os.makedirs(p, exist_ok=True)

os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
mlflow.set_tracking_uri(f'file://{MLFLOW_DIR}')
mlflow.set_experiment('MedAssist_V6_Phase2')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('=' * 60)
print(f'  MedAssist AI - Training Phase 2 {VERSION}')
print(f'  Device: {device} | PyTorch: {torch.__version__}')
print('=' * 60)
# ── FREE COLAB SAFE: Stream-extract from Drive (no temp copy) ─────────────────
import zipfile
from tqdm.auto import tqdm


# ────────────────────────────────────────────────────────────
# ## CELL 1 — SSD Optimization: Copy All Datasets to Local NVMe


# ── Cell 5 ───────────────────────────────────────
def stream_extract_zip(zip_path, dest_dir, batch_size=500, label='Dataset'):
    """Extract zip DIRECTLY from Drive to SSD — no cp, no temp file.

    • Reads from Drive mount → writes to Colab SSD one file at a time
    • Resumes automatically (skips files already on SSD)
    • Periodic gc.collect() to keep RAM low on Free Colab
    """
    os.makedirs(dest_dir, exist_ok=True)
    existing = set(os.listdir(dest_dir)) if os.path.isdir(dest_dir) else set()

    with zipfile.ZipFile(zip_path, 'r') as zf:
        members = [m for m in zf.namelist()
                   if not m.endswith('/') and os.path.basename(m)]
        to_extract = [m for m in members if os.path.basename(m) not in existing]

        if not to_extract:
            print(f'  ✅ {label}: all {len(existing):,} files already on SSD — skipping')
            return len(existing)

        print(f'  📦 {label}: extracting {len(to_extract):,}/{len(members):,} files '
              f'(resuming {len(existing):,} already done)...')

        for i, member in enumerate(tqdm(to_extract, desc=f'{label} → SSD')):
            data = zf.read(member)
            fname = os.path.basename(member)
            with open(os.path.join(dest_dir, fname), 'wb') as f:
                f.write(data)
            del data                       # free immediately

            if (i + 1) % batch_size == 0:
                gc.collect()               # keep RAM low

    gc.collect()
    n_final = len(os.listdir(dest_dir))
    print(f'  ✅ {label}: {n_final:,} files ready at {dest_dir}')
    return n_final


# ── PAD-UFES-20 images → SSD ─────────────────────────────────────────────────
ZIP_IN_DRIVE = '/content/drive/MyDrive/MedAssist_AI/dataset/images.zip'
LOCAL_IMAGES = '/content/local_dataset/images'

if os.path.isdir(LOCAL_IMAGES) and len(os.listdir(LOCAL_IMAGES)) >= 2000:
    print(f'✅ PAD-UFES-20 SSD ready ({len(os.listdir(LOCAL_IMAGES)):,} files) — skipping')
elif os.path.exists(ZIP_IN_DRIVE):
    stream_extract_zip(ZIP_IN_DRIVE, LOCAL_IMAGES, batch_size=500, label='PAD-UFES-20')
else:
    print(f'⚠️  PAD-UFES-20 zip not found — run 00_setup first: {ZIP_IN_DRIVE}')

images_dir = LOCAL_IMAGES
if not os.path.isdir(images_dir) or not os.listdir(images_dir):
    print('WARNING: local SSD not found, falling back to Drive...')
    images_dir = os.path.join(DATASET_PATH, 'images')
print(f'Dataset ready at: {images_dir}')
# ── ISIC 2019 → SSD (stream, no cp) ──────────────────────────────────────────


# ────────────────────────────────────────────────────────────
# ## CELL 2 — Load ISIC 2019 to SSD


# ── Cell 7 ───────────────────────────────────────
ISIC_ZIP_DRIVE = '/content/drive/MyDrive/MedAssist_AI/dataset_isic2019/isic_2019_images.zip'
LOCAL_ISIC_DIR = '/content/local_dataset/isic2019'

if os.path.isdir(LOCAL_ISIC_DIR) and len(os.listdir(LOCAL_ISIC_DIR)) >= 2000:
    print(f'✅ ISIC SSD ready ({len(os.listdir(LOCAL_ISIC_DIR)):,} files) — skipping')
elif os.path.exists(ISIC_ZIP_DRIVE):
    print(f'📦 ISIC 2019 zip on Drive: {os.path.getsize(ISIC_ZIP_DRIVE)/(1024**2):.0f} MB')
    stream_extract_zip(ISIC_ZIP_DRIVE, LOCAL_ISIC_DIR, batch_size=300,
                       label='ISIC 2019')
else:
    print(f'⚠️  ISIC zip not found — run 00_setup first: {ISIC_ZIP_DRIVE}')
    LOCAL_ISIC_DIR = None
# ── MCR-SL → SSD (stream, no cp) ─────────────────────────────────────────────


# ────────────────────────────────────────────────────────────
# ## CELL 3 — Load MCR-SL to SSD


# ── Cell 9 ───────────────────────────────────────
MCR_ZIP_DRIVE = '/content/drive/MyDrive/MedAssist_AI/dataset_mcr_sl/mcr_sl_images.zip'
LOCAL_MCR_DIR = '/content/local_dataset/mcr_sl'

if os.path.isdir(LOCAL_MCR_DIR) and len(os.listdir(LOCAL_MCR_DIR)) >= 2000:
    print(f'✅ MCR-SL SSD ready ({len(os.listdir(LOCAL_MCR_DIR)):,} files) — skipping')
elif os.path.exists(MCR_ZIP_DRIVE):
    print(f'📦 MCR-SL zip on Drive: {os.path.getsize(MCR_ZIP_DRIVE)/(1024**2):.0f} MB')
    stream_extract_zip(MCR_ZIP_DRIVE, LOCAL_MCR_DIR, batch_size=300,
                       label='MCR-SL')
else:
    print(f'⚠️  MCR-SL zip not found — run 00_setup first: {MCR_ZIP_DRIVE}')
    LOCAL_MCR_DIR = None


# ────────────────────────────────────────────────────────────
# ## CELL 4 — Load Config & Model Architecture V6.0 (GatedCrossAttentionFusion + MedAssistModel)


# ── Cell 11 ───────────────────────────────────────
# --- Load Config ---
with open(os.path.join(PROCESSED_PATH, 'preprocessing_config.json'), 'r') as f:
    config = json.load(f)
assert config['version'] == 'V6.0'
NUM_CLASSES = config['num_classes']
NUM_META = config['num_meta_features']
CLASS_NAMES = config['class_names']
IMG_SIZE = config['img_size']
SELECTED_FEATS = config['selected_features']
NORM_MEAN = config['normalization']['mean']
NORM_STD = config['normalization']['std']

class_weights_np = np.load(os.path.join(PROCESSED_PATH, 'class_weights.npy'))
weights_tensor = torch.tensor(class_weights_np, dtype=torch.float32).to(device)
print(f'Config V6.0: {NUM_META} features, {NUM_CLASSES} classes, img={IMG_SIZE}')


# ============================================================
# Model Architecture (identical to 04a with meta_mask fixes)
# ============================================================
import math

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
        self.backbone = timm.create_model(backbone_name, pretrained=False, num_classes=0, global_pool='')
        backbone_dim = self.backbone.num_features
        self.projection = nn.Sequential(
            nn.Conv2d(backbone_dim, 512, 1), nn.BatchNorm2d(512), nn.GELU(),
            nn.Conv2d(512, embed_dim, 1), nn.BatchNorm2d(embed_dim),
        )
        self.auxiliary_head = nn.Sequential(
            GeM(p=3.0), nn.Flatten(),          # ✅ إصلاح
            nn.Linear(backbone_dim, 256), nn.GELU(), nn.Dropout(0.3), nn.Linear(256, num_classes)
        )
        self.pool = nn.AdaptiveAvgPool2d(7)
        self.embed_dim = embed_dim

    def forward(self, x):
        features = self.backbone(x)
        if 'swin' in self.backbone_name:
            if features.dim() == 3:
                B, L, C = features.shape
                H = W = int(math.sqrt(L))
                features = features.transpose(1, 2).view(B, C, H, W)
            elif features.dim() == 4 and features.shape[1] == features.shape[2]:
                features = features.permute(0, 3, 1, 2)
        aux_logits = self.auxiliary_head(features)
        pooled = self.pool(features)
        projected = self.projection(pooled)
        B, C, H, W = projected.shape
        patches = projected.view(B, C, H*W).permute(0, 2, 1)
        return patches, aux_logits, features


class MLPBranch(nn.Module):
    def __init__(self, num_features=7, embed_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(num_features, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(128, 64), nn.LayerNorm(64), nn.GELU(), nn.Dropout(0.35),
            nn.Linear(64, embed_dim),
        )

    def forward(self, x, meta_mask=None):
        if meta_mask is not None:
            x = x * meta_mask.float()
        return self.net(x)


class GatedCrossAttentionFusion(nn.Module):
    def __init__(self, img_embed_dim=256, meta_embed_dim=64, num_classes=6, num_heads=4):
        super().__init__()
        self.embed_dim = img_embed_dim
        self.meta_proj = nn.Sequential(nn.Linear(meta_embed_dim, img_embed_dim), nn.LayerNorm(img_embed_dim))
        self.img_norm = nn.LayerNorm(img_embed_dim)
        self.pos_embed = nn.Parameter(torch.zeros(1, 49, img_embed_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        self.cross_attn = nn.MultiheadAttention(embed_dim=img_embed_dim, num_heads=num_heads, dropout=0.1, batch_first=True)
        self.img_global_pool_proj = nn.Sequential(nn.Linear(img_embed_dim, img_embed_dim), nn.LayerNorm(img_embed_dim))
        self.gate = nn.Sequential(nn.Linear(img_embed_dim * 2, img_embed_dim), nn.Sigmoid())
        self.classifier = nn.Sequential(
            nn.Linear(img_embed_dim, 256), nn.LayerNorm(256), nn.GELU(), nn.Dropout(0.55),
            nn.Linear(256, 128), nn.LayerNorm(128), nn.GELU(), nn.Dropout(0.45),
            nn.Linear(128, num_classes)
        )

    def forward(self, patches, meta_emb):
        meta_q = self.meta_proj(meta_emb).unsqueeze(1)
        patches_norm = self.img_norm(patches + self.pos_embed)
        attended, _ = self.cross_attn(meta_q, patches_norm, patches_norm)
        attended = attended.squeeze(1)
        img_global = self.img_global_pool_proj(patches.mean(dim=1))
        g = self.gate(torch.cat([attended, img_global], dim=-1))
        fused = g * attended + (1 - g) * img_global
        return self.classifier(fused), g.unsqueeze(1)


class MedAssistModel(nn.Module):
    def __init__(self, num_meta=7, num_classes=6, img_embed_dim=256, meta_embed_dim=64, backbone_name='efficientnet_b3'):
        super().__init__()
        self.image_branch = ImageBranch(num_classes=num_classes, embed_dim=img_embed_dim, backbone_name=backbone_name)
        self.mlp_branch   = MLPBranch(num_features=num_meta, embed_dim=meta_embed_dim)
        self.fusion        = GatedCrossAttentionFusion(img_embed_dim, meta_embed_dim, num_classes, num_heads=4)

    def forward(self, images, metadata, meta_mask=None):
        patches, aux_logits, _ = self.image_branch(images)
        meta_emb = self.mlp_branch(metadata, meta_mask)
        main_logits, gate = self.fusion(patches, meta_emb)
        return main_logits, aux_logits, gate


print('✅ MedAssistModel V6.0 defined')


# ============================================================
# Load Phase 1 State + Best Checkpoint
# ============================================================
phase1_state_path = os.path.join(RESULTS_PATH, 'phase1_state.json')
assert os.path.exists(phase1_state_path), '❌ phase1_state.json not found! Run 04a first.'
with open(phase1_state_path) as f:
    p1_state = json.load(f)
phase1_epochs_done = p1_state['total_epochs_trained']
phase1_best_f1     = p1_state['best_f1']
best_ckpts = sorted(glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase1_f1_*.pth')))
assert best_ckpts, '❌ No Phase 1 checkpoint found! Run 04a first.'
ckpt = torch.load(best_ckpts[-1], map_location=device)
model = MedAssistModel(num_meta=NUM_META, num_classes=NUM_CLASSES).to(device)
model.load_state_dict(ckpt['model_state_dict'])
print(f'✅ Loaded Phase 1 checkpoint: F1={phase1_best_f1:.4f}, epochs done={phase1_epochs_done}')


# --- V6.0 Preprocessing ---


# ────────────────────────────────────────────────────────────
# ## CELL 5 — V6.0 Preprocessing Functions & Transforms


# ── Cell 13 ───────────────────────────────────────
def shades_of_gray(img, power=6):
    img_f = img.astype(np.float32) + 1e-7
    if power == -1:
        norm = np.max(img_f, axis=(0, 1))
    else:
        norm = np.power(np.mean(np.power(img_f, power), axis=(0, 1)), 1.0 / power)
    norm = norm + 1e-7
    result = img_f / norm * np.mean(norm)
    return np.clip(result, 0, 255).astype(np.uint8)

def dullrazor_hair_removal(img, kernel_size=17, threshold=10):
    """Optimized DullRazor hair removal (FAST)."""
    # 1. Find the hair
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    _, hair_mask = cv2.threshold(blackhat, threshold, 255, cv2.THRESH_BINARY)

    # 2. FAST INPAINTING: Create a blurred version of the image
    # and only replace the exact pixels where the hair mask is true.
    blurred_img = cv2.medianBlur(img, 15) # Fast median filter

    # Expand mask to 3 channels so it matches the image shape
    hair_mask_3d = np.expand_dims(hair_mask, axis=-1)

    # Where mask is white (hair), use blurred background. Otherwise, use original.
    result = np.where(hair_mask_3d > 0, blurred_img, img)

    return result.astype(np.uint8)


# --- Transforms ---
train_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=45, p=0.7),
    A.HorizontalFlip(p=0.5), A.VerticalFlip(p=0.5),
    A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.5),
    A.CoarseDropout(max_holes=8, max_height=32, max_width=32, fill_value=0, p=0.5),
    A.ElasticTransform(alpha=1, sigma=50, alpha_affine=50, p=0.3),
    A.GridDistortion(num_steps=5, distort_limit=0.3, p=0.3),
    A.CLAHE(clip_limit=2.0, p=1.0),
    A.OneOf([
        A.Solarize(threshold=128, p=1.0),
        A.Posterize(num_bits=4, p=1.0),
        A.Equalize(p=1.0),
        A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1.0), p=1.0),
        A.GaussianBlur(blur_limit=(3, 5), p=1.0),
    ], p=0.3),
    A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.4),
    A.Normalize(mean=NORM_MEAN, std=NORM_STD), ToTensorV2()
])
val_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE), A.CLAHE(clip_limit=2.0, p=1.0),
    A.Normalize(mean=NORM_MEAN, std=NORM_STD), ToTensorV2()
])
# --- Dataset ---


# ────────────────────────────────────────────────────────────
# ## CELL 6 — SkinLesionDataset (PAD + ISIC + MCR)


# ── Cell 15 ───────────────────────────────────────
class SkinLesionDataset(Dataset):
    """V6.0 Dataset — searches PAD-UFES-20 + ISIC 2019 + MCR-SL image dirs."""

    def __init__(self, df, images_dir, metadata_cols, transform=None):
        self.df = df.reset_index(drop=True)
        self.images_dir = images_dir
        self.transform = transform
        self.metadata_cols = metadata_cols
        self.img_paths = {}

        # PAD-UFES-20: nested subdirs
        for sub in ['imgs_part_1/imgs_part_1','imgs_part_2/imgs_part_2','imgs_part_3/imgs_part_3']:
            full_dir = os.path.join(images_dir, sub)
            if os.path.isdir(full_dir):
                for fname in os.listdir(full_dir):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                        self.img_paths[fname] = os.path.join(full_dir, fname)
        # PAD-UFES-20: flat directory
        if os.path.isdir(images_dir):
            for fname in os.listdir(images_dir):
                if fname.lower().endswith(('.png', '.jpg', '.jpeg')) and fname not in self.img_paths:
                    self.img_paths[fname] = os.path.join(images_dir, fname)

        # ISIC 2019: /content/local_dataset/isic2019/
        isic_dir = '/content/local_dataset/isic2019'
        if os.path.isdir(isic_dir):
            for fname in os.listdir(isic_dir):
                if fname.lower().endswith(('.png', '.jpg', '.jpeg')) and fname not in self.img_paths:
                    self.img_paths[fname] = os.path.join(isic_dir, fname)

        # MCR-SL: /content/local_dataset/mcr_sl/
        mcr_dir = '/content/local_dataset/mcr_sl'
        if os.path.isdir(mcr_dir):
            for fname in os.listdir(mcr_dir):
                if fname.lower().endswith(('.png', '.jpg', '.jpeg')) and fname not in self.img_paths:
                    self.img_paths[fname] = os.path.join(mcr_dir, fname)

        missing = [f for f in df['img_filename'].values if f not in self.img_paths]
        if missing:
            print(f'⚠️  WARNING: {len(missing)} images not found! First 5: {missing[:5]}')
        else:
            print(f'✅ All {len(df)} images found ({len(self.img_paths):,} total in lookup)')

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_filename = row['img_filename']

        CACHE_DIR = '/content/fast_images'
        cache_path = os.path.join(CACHE_DIR, img_filename)

        if not os.path.exists(cache_path):
            # Graceful fallback: preprocess on-the-fly from raw SSD path
            raw_path = self.img_paths.get(img_filename)
            if raw_path is None or not os.path.exists(raw_path):
                raise FileNotFoundError(
                    f"Image not found in cache OR raw SSD: {img_filename}. "
                    f"Re-run CELL 1 (SSD extract) then CELL 6 (Pre-cache)."
                )
            img = cv2.imread(raw_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)
            img = shades_of_gray(img, power=6)
            img = dullrazor_hair_removal(img, kernel_size=17, threshold=10)
            os.makedirs(CACHE_DIR, exist_ok=True)
            cv2.imwrite(cache_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        else:
            img = cv2.imread(cache_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.transform:
            img = self.transform(image=img)['image']

        meta  = torch.FloatTensor(row[self.metadata_cols].values.astype(float))
        label = int(row['label'])
        clinical_ok = bool(row.get('clinical_complete', True))
        if clinical_ok:
            meta_mask = torch.ones(len(self.metadata_cols), dtype=torch.float32)
        else:
            meta_mask = torch.tensor([1, 1, 0, 0, 0, 0, 0], dtype=torch.float32)
        return img, meta, meta_mask, label, img_filename
# --- DataLoaders ---


# ────────────────────────────────────────────────────────────
# ## CELL 6.5 — DataLoaders Finalize


# ── Cell 17 ───────────────────────────────────────
train_df = pd.read_csv(os.path.join(PROCESSED_PATH, 'train.csv'))
val_df = pd.read_csv(os.path.join(PROCESSED_PATH, 'val.csv'))
train_dataset = SkinLesionDataset(train_df, images_dir, SELECTED_FEATS, train_transforms)
val_dataset = SkinLesionDataset(val_df, images_dir, SELECTED_FEATS, val_transforms)

sample_weights = np.array([class_weights_np[l] for l in train_df['label'].values])
sample_weights = sample_weights / sample_weights.sum()
sampler = WeightedRandomSampler(torch.DoubleTensor(sample_weights), len(train_dataset), replacement=True)

BATCH_SIZE = 32
train_loader = DataLoader(
    train_dataset, batch_size=BATCH_SIZE, sampler=sampler,
    num_workers=2, pin_memory=True, persistent_workers=True,
    prefetch_factor=2, drop_last=True
)

val_loader = DataLoader(
    val_dataset, batch_size=BATCH_SIZE, shuffle=False,
    num_workers=2, pin_memory=True, persistent_workers=True,
    prefetch_factor=2
)


# ────────────────────────────────────────────────────────────
# ## CELL 7 — Pre-Cache Cell + WeightedFocalLoss Setup


# ── Cell 19 ───────────────────────────────────────
##Cell 5.5 Pre-Cache Cell

assert 'train_dataset' in globals(), "❌ Run CELL 6 (DataLoaders) first before pre-caching!"

import concurrent.futures
from tqdm.auto import tqdm
import cv2
import os

CACHE_DIR = '/content/fast_images'
os.makedirs(CACHE_DIR, exist_ok=True)

def process_and_cache(args):
    img_filename, img_path = args
    cache_path = os.path.join(CACHE_DIR, img_filename)

    # Skip if already done (makes restarting instant)
    if os.path.exists(cache_path):
        return 'skip'

    img = cv2.imread(img_path)
    if img is None:
        return 'fail'

    # Pre-resize to 256x256 first. This reduces pixel operations by up to 16x,
    # making preprocessing (Shades of Gray, DullRazor) and disk writes extremely fast.
    img = cv2.resize(img, (256, 256), interpolation=cv2.INTER_AREA)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = shades_of_gray(img, power=6)
    img = dullrazor_hair_removal(img, kernel_size=17, threshold=10)

    cv2.imwrite(cache_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return 'ok'

# Gather only the specific images needed by the active datasets to avoid caching all 29k+ images
all_items = []
needed_filenames = set()

if 'train_df' in globals():
    needed_filenames.update(train_df['img_filename'].dropna().tolist())
elif 'train_dataset' in globals():
    needed_filenames.update(train_dataset.df['img_filename'].dropna().tolist())

if 'val_df' in globals():
    needed_filenames.update(val_df['img_filename'].dropna().tolist())
elif 'val_dataset' in globals():
    needed_filenames.update(val_dataset.df['img_filename'].dropna().tolist())

if 'test_df' in globals():
    needed_filenames.update(test_df['img_filename'].dropna().tolist())
elif 'test_dataset' in globals():
    needed_filenames.update(test_dataset.df['img_filename'].dropna().tolist())

for f in needed_filenames:
    path = None
    if 'train_dataset' in globals() and f in train_dataset.img_paths:
        path = train_dataset.img_paths[f]
    elif 'val_dataset' in globals() and f in val_dataset.img_paths:
        path = val_dataset.img_paths[f]
    elif 'test_dataset' in globals() and f in test_dataset.img_paths:
        path = test_dataset.img_paths[f]

    if path:
        all_items.append((f, path))

if all_items:
    print(f'Starting cache for {len(all_items)} images...')
    CACHE_BATCH = 200
    counts = {'ok': 0, 'skip': 0, 'fail': 0}
    for batch_start in range(0, len(all_items), CACHE_BATCH):
        batch = all_items[batch_start:batch_start + CACHE_BATCH]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(tqdm(
                executor.map(process_and_cache, batch),
                total=len(batch),
                desc=f'Caching [{batch_start+1}-{batch_start+len(batch)}/{len(all_items)}]'
            ))
        for r in results:
            counts[r] = counts.get(r, 0) + 1
        gc.collect()
    print(f'Cache complete: {counts}')
else:
    print('No datasets found to cache.')

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

# alpha=None: class balance handled by WeightedRandomSampler
criterion = WeightedFocalLoss(
    alpha=None, gamma=2.0, label_smoothing=0.05).to(device)


# ────────────────────────────────────────────────────────────
# ## CELL 8 — Phase 2 Hyperparameters, Optimizer, Scheduler & SWA


# ── Cell 21 ───────────────────────────────────────
# --- Phase 2 Hyperparameters ---
LR_BACKBONE = 5e-6
LR_HEAD = 5e-5
WEIGHT_DECAY = 0.1
NUM_EPOCHS_P2 = 45  # epochs 36-80 (extended for SWA convergence)
EPOCH_OFFSET = phase1_epochs_done  # for display
WARMUP_EPOCHS = 3
PATIENCE = 20
MIN_DELTA = 0.001   # ✅ إضافة: حد أدنى للتحسن المعتبر
GRAD_CLIP = 1.0
SWA_START_EPOCH = 15  # epoch 15 of phase2 = global epoch 50
SWA_LR = 1e-6

backbone_params = list(model.image_branch.backbone.parameters())
backbone_ids = set(id(p) for p in backbone_params)
head_params = [p for p in model.parameters() if id(p) not in backbone_ids]

optimizer = torch.optim.AdamW([
    {'params': backbone_params, 'lr': LR_BACKBONE},
    {'params': head_params, 'lr': LR_HEAD},
], weight_decay=WEIGHT_DECAY)

total_steps = NUM_EPOCHS_P2 * len(train_loader)
warmup_steps = WARMUP_EPOCHS * len(train_loader)

# Task 3.3: Cosine Annealing with Warm Restarts
scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
    optimizer,
    T_0=10,
    T_mult=1,
    eta_min=1e-6
)
scaler = GradScaler()

# SWA setup
swa_model = AveragedModel(model)
swa_scheduler = SWALR(optimizer, swa_lr=SWA_LR)
swa_active = False

print(f'Phase 2: {NUM_EPOCHS_P2} epochs (global {EPOCH_OFFSET+1}-{EPOCH_OFFSET+NUM_EPOCHS_P2})')
print(f'LR: backbone={LR_BACKBONE}, head={LR_HEAD}')
print(f'SWA starts at phase2 epoch {SWA_START_EPOCH} (global epoch {EPOCH_OFFSET+SWA_START_EPOCH})')

# --- CutMix ---
def rand_bbox(size, lam):
    W = size[2]
    H = size[3]
    cut_rat = np.sqrt(1. - lam)
    cut_w = int(W * cut_rat)
    cut_h = int(H * cut_rat)
    cx = np.random.randint(W)
    cy = np.random.randint(H)
    bbx1 = np.clip(cx - cut_w // 2, 0, W)
    bby1 = np.clip(cy - cut_h // 2, 0, H)
    bbx2 = np.clip(cx + cut_w // 2, 0, W)
    bby2 = np.clip(cy + cut_h // 2, 0, H)
    return bbx1, bby1, bbx2, bby2

def cutmix_data(images, metadata, labels, alpha=1.0, p=0.5):
    """Task 3.2: Apply CutMix Augmentation"""
    if np.random.random() > p:
        return images, metadata, labels, None

    batch_size = images.size(0)
    lam = np.random.beta(alpha, alpha)
    indices = torch.randperm(batch_size).to(images.device)

    bbx1, bby1, bbx2, bby2 = rand_bbox(images.size(), lam)
    mixed_images = images.clone()
    indices_imgs = images[indices].clone()
    mixed_images[:, :, bbx1:bbx2, bby1:bby2] = indices_imgs[:, :, bbx1:bbx2, bby1:bby2]
    lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (images.size()[-1] * images.size()[-2]))

    mixed_metadata = lam * metadata + (1 - lam) * metadata[indices]

    num_classes = NUM_CLASSES
    labels_onehot = F.one_hot(labels, num_classes).float()
    labels_b_onehot = F.one_hot(labels[indices], num_classes).float()
    mixed_labels = lam * labels_onehot + (1 - lam) * labels_b_onehot

    return mixed_images, mixed_metadata, mixed_labels, lam

def compute_mixup_loss(logits, mixed_labels, criterion_fn):
    log_probs = F.log_softmax(logits, dim=-1)
    return -(mixed_labels * log_probs).sum(dim=-1).mean()

# --- Train / Val functions ---


# ────────────────────────────────────────────────────────────
# ## CELL 9 — Main Training Loop (Phase 2 + MLflow)


# ── Cell 23 ───────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, scheduler, scaler, device, epoch, global_epoch, use_swa_sched):
    model.train()
    running_loss = 0.0
    all_preds, all_labels = [], []
    pbar = tqdm(loader, desc=f'Epoch {global_epoch:02d} [Train]', leave=False)
    for images, meta, meta_mask, labels, _ in pbar:
        images    = images.to(device, non_blocking=True)
        meta      = meta.to(device, non_blocking=True)
        meta_mask = meta_mask.to(device, non_blocking=True)
        labels    = labels.to(device, non_blocking=True)
        mixed_images, mixed_meta, mixed_labels, lam = cutmix_data(images, meta, labels, alpha=1.0, p=0.3)
        optimizer.zero_grad(set_to_none=True)
        with autocast():
            main_logits, aux_logits, gate = model(mixed_images, mixed_meta, meta_mask)
            if lam is not None:
                main_loss = compute_mixup_loss(main_logits, mixed_labels, criterion)
                aux_loss = compute_mixup_loss(aux_logits, mixed_labels, criterion)
            else:
                main_loss = criterion(main_logits, labels)
                aux_loss = criterion(aux_logits, labels)
            loss = 0.7 * main_loss + 0.3 * aux_loss
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        scaler.step(optimizer)
        scaler.update()
        running_loss += loss.item() * images.size(0)
        with torch.no_grad():
            preds = main_logits.argmax(dim=1)
            if lam is None:
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
        cur_lr = optimizer.param_groups[0]['lr']
        pbar.set_postfix({'loss': f'{loss.item():.4f}', 'lr': f'{cur_lr:.2e}'})
    epoch_loss = running_loss / len(loader.dataset)
    epoch_f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
    return epoch_loss, epoch_f1

@torch.no_grad()
def validate(model, loader, criterion, device, use_tta: bool = False):
    """Validate — مع TTA×4 اختياري من epoch 10 لـ checkpoint selection أدق."""
    _TTA_FNS = [
        lambda x: x,
        lambda x: torch.flip(x, dims=[3]),        # Horizontal Flip
        lambda x: torch.flip(x, dims=[2]),        # Vertical Flip
        lambda x: torch.rot90(x, k=1, dims=[2, 3]),  # Rotate 90°
    ]
    model.eval()
    running_loss = 0.0
    all_preds, all_labels = [], []

    for images, meta, meta_mask, labels, _ in loader:
        images    = images.to(device, non_blocking=True)
        meta      = meta.to(device, non_blocking=True)
        meta_mask = meta_mask.to(device, non_blocking=True)
        labels    = labels.to(device, non_blocking=True)

        if use_tta:
            probs_sum = torch.zeros(images.size(0), NUM_CLASSES, device=device)
            for aug_fn in _TTA_FNS:
                with autocast():
                    logits, _, _ = model(aug_fn(images), meta, meta_mask)
                probs_sum += torch.softmax(logits, dim=-1)
            preds = (probs_sum / len(_TTA_FNS)).argmax(dim=1)
            with autocast():
                main_logits, aux_logits, _ = model(images, meta, meta_mask)
                loss = 0.7 * criterion(main_logits, labels) + \
                       0.3 * criterion(aux_logits, labels)
        else:
            with autocast():
                main_logits, aux_logits, _ = model(images, meta, meta_mask)
                loss = 0.7 * criterion(main_logits, labels) + \
                       0.3 * criterion(aux_logits, labels)
            preds = main_logits.argmax(dim=1)

        running_loss += loss.item() * images.size(0)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

    epoch_loss = running_loss / len(loader.dataset)
    epoch_f1   = f1_score(all_labels, all_preds, average='macro', zero_division=0)
    return epoch_loss, epoch_f1, all_preds, all_labels
# --- Main Training Loop ---
print('\n' + '=' * 60)
print('  STARTING PHASE 2 TRAINING')
print('=' * 60 + '\n')

best_f1 = phase1_best_f1
best_epoch = 0
patience_counter = 0
history = []
start_epoch_p2 = 1
start_time = time.time()

# --- Auto-Resume: Load last Phase 2 checkpoint if session was interrupted ---
resume_ckpts_p2 = sorted(glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase2_f1_*.pth')))
if resume_ckpts_p2:
    resume_ckpt = torch.load(resume_ckpts_p2[-1], map_location=device)
    model.load_state_dict(resume_ckpt['model_state_dict'])
    optimizer.load_state_dict(resume_ckpt['optimizer_state_dict'])
    resumed_global_epoch = resume_ckpt['epoch']
    start_epoch_p2 = resumed_global_epoch - EPOCH_OFFSET + 1
    best_f1 = resume_ckpt['best_f1']
    best_epoch = resumed_global_epoch
    # Activate SWA if we're past the SWA start
    if start_epoch_p2 >= SWA_START_EPOCH:
        swa_active = True
    print(f'🔄 RESUMED Phase 2 from global epoch {resumed_global_epoch}, best F1={best_f1:.4f}')
    print(f'   Continuing from phase2 epoch {start_epoch_p2} → {NUM_EPOCHS_P2}')
else:
    print('🆕 Starting Phase 2 fresh (no phase2 checkpoint found)')

with mlflow.start_run(run_name='MedAssist_V6.0_Phase2'):
    mlflow.log_params({
        'version': VERSION, 'phase': 'phase2', 'num_epochs': NUM_EPOCHS_P2,
        'batch_size': BATCH_SIZE, 'lr_backbone': LR_BACKBONE, 'lr_head': LR_HEAD,
        'weight_decay': WEIGHT_DECAY, 'patience': PATIENCE, 'grad_clip': GRAD_CLIP,
        'swa_start_epoch': SWA_START_EPOCH, 'swa_lr': SWA_LR,
        'phase1_best_f1': phase1_best_f1, 'cutmix_p': 0.3, 'cutmix_alpha': 1.0,
        'resumed_from_epoch': start_epoch_p2 - 1,
    })

    for epoch in range(start_epoch_p2, NUM_EPOCHS_P2 + 1):
        global_epoch = EPOCH_OFFSET + epoch
        use_swa_sched = epoch >= SWA_START_EPOCH

        # Activate SWA
        if epoch == SWA_START_EPOCH and not swa_active:
            swa_active = True
            print(f'\n>>> SWA ACTIVATED at epoch {global_epoch} <<<\n')
            patience_counter = 0

        train_loss, train_f1 = train_one_epoch(
            model, train_loader, criterion, optimizer, scheduler, scaler, device, epoch, global_epoch, use_swa_sched
        )

        # SWA scheduler step (per epoch) and model update
        if swa_active:
            swa_scheduler.step()
            swa_model.update_parameters(model)
        else:
            scheduler.step()

        _use_tta = (epoch >= 5)    # ✅ Phase 2 أقصر — TTA من epoch 5
        val_loss, val_f1, val_preds, val_labels = validate(
            model, val_loader, criterion, device, use_tta=_use_tta
        )

        current_lr = optimizer.param_groups[0]['lr']
        mlflow.log_metrics({
            'train_loss': train_loss, 'train_f1': train_f1,
            'val_loss': val_loss, 'val_f1': val_f1, 'learning_rate': current_lr,
        }, step=global_epoch)

        history.append({
            'epoch': global_epoch, 'phase2_epoch': epoch,
            'train_loss': train_loss, 'train_f1': train_f1,
            'val_loss': val_loss, 'val_f1': val_f1,
            'best_f1': max(best_f1, val_f1), 'lr': current_lr, 'swa_active': swa_active,
        })

        if val_f1 > best_f1 + MIN_DELTA:   # ✅ إصلاح: تحسن حقيقي فقط
            best_f1 = val_f1
            best_epoch = global_epoch
            patience_counter = 0
            ckpt_name = f'best_model_V6.0_phase2_f1_{val_f1:.4f}.pth'
            ckpt_path = os.path.join(MODELS_PATH, ckpt_name)
            old_ckpts = glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase2_f1_*.pth'))
            for old in old_ckpts:
                os.remove(old)
            torch.save({
                'epoch': global_epoch, 'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'best_f1': best_f1, 'val_loss': val_loss,
            }, ckpt_path)
            print(f'  >> New best! F1={val_f1:.4f} saved to {ckpt_name}')
        else:
            patience_counter += 1

        swa_tag = ' [SWA]' if swa_active else ''
        print(f'Epoch {global_epoch:02d} | Loss:{train_loss:.4f} | ValF1:{val_f1:.4f} | '
              f'Best:{best_f1:.4f} | LR:{current_lr:.2e} | Pat:{patience_counter}/{PATIENCE}{swa_tag}')

        if patience_counter >= PATIENCE:
            print(f'\nEarly stopping at epoch {global_epoch}')
            break

    elapsed = time.time() - start_time
    print(f'\nPhase 2 training complete in {elapsed/60:.1f} minutes')
    print(f'Best F1: {best_f1:.4f} at epoch {best_epoch}')
    mlflow.log_metrics({'best_f1': best_f1, 'best_epoch': best_epoch})
# --- Update SWA BN and Save ---
print('\nUpdating SWA BatchNorm statistics...')
torch.cuda.empty_cache()



# ────────────────────────────────────────────────────────────
# ## CELL 10 — Custom SWA BatchNorm Update


# ── Cell 25 ───────────────────────────────────────
# --- CUSTOM SWA BN UPDATE ---
@torch.no_grad()
def custom_update_bn(loader, model, device=None):
    momenta = {}
    for module in model.modules():
        if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
            module.running_mean = torch.zeros_like(module.running_mean)
            module.running_var = torch.ones_like(module.running_var)
            momenta[module] = module.momentum

    if not momenta:
        return

    was_training = model.training
    model.train()
    for module in momenta.keys():
        module.momentum = None
        module.num_batches_tracked *= 0

    for images, meta, meta_mask, labels, _ in loader:
        if device is not None:
            images = images.to(device)
            meta = meta.to(device)
            meta_mask = meta_mask.to(device)
        model(images, meta, meta_mask)

    for module in momenta.keys():
        module.momentum = momenta[module]
    model.train(was_training)

custom_update_bn(train_loader, swa_model, device=device)

swa_path = os.path.join(MODELS_PATH, 'swa_model_V6.0.pth')
torch.save(swa_model.module.state_dict(), swa_path)
print(f'SWA model saved to {swa_path}')

# Validate SWA model
swa_val_loss, swa_val_f1, _, _ = validate(swa_model, val_loader, criterion, device)
print(f'SWA model val F1: {swa_val_f1:.4f} (vs best phase2: {best_f1:.4f})')


# ────────────────────────────────────────────────────────────
# ## CELL 11 — Per-Class Thresholds & Save State


# ── Cell 27 ───────────────────────────────────────
# --- Per-class Threshold Optimization ---
print('\n' + '=' * 60)
print('  PER-CLASS THRESHOLD OPTIMIZATION')
print('=' * 60)

# Use best model for threshold optimization
best_ckpts = sorted(glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase2_f1_*.pth')))
if best_ckpts:
    best_ckpt = torch.load(best_ckpts[-1], map_location=device)
    model.load_state_dict(best_ckpt['model_state_dict'])
    print(f'Loaded best phase2 model for threshold optimization')

model.eval()
all_probs, all_labels_th = [], []
with torch.no_grad():
    for images, meta, meta_mask, labels, _ in tqdm(val_loader, desc='Collecting probs'):
        images = images.to(device, non_blocking=True)
        meta = meta.to(device, non_blocking=True)
        meta_mask = meta_mask.to(device, non_blocking=True)
        with autocast():
            main_logits, _, _ = model(images, meta, meta_mask)
        probs = F.softmax(main_logits, dim=-1)
        all_probs.append(probs.cpu().numpy())
        all_labels_th.extend(labels.numpy())

all_probs = np.concatenate(all_probs, axis=0)
all_labels_th = np.array(all_labels_th)

# Greedy sequential threshold optimization
thresholds = np.ones(NUM_CLASSES)
threshold_range = np.arange(0.10, 0.825, 0.025)

for c in range(NUM_CLASSES):
    best_thresh_f1 = 0.0
    best_thresh = 1.0
    for thresh in threshold_range:
        adjusted_probs = all_probs.copy()
        # Apply previously optimized thresholds
        for prev_c in range(c):
            adjusted_probs[:, prev_c] = adjusted_probs[:, prev_c] / thresholds[prev_c]
        # Apply current candidate threshold
        adjusted_probs[:, c] = adjusted_probs[:, c] / thresh
        preds = adjusted_probs.argmax(axis=1)
        f1 = f1_score(all_labels_th, preds, average='macro', zero_division=0)
        if f1 > best_thresh_f1:
            best_thresh_f1 = f1
            best_thresh = thresh
    thresholds[c] = best_thresh
    print(f'  {CLASS_NAMES[c]}: threshold={best_thresh:.3f} (F1={best_thresh_f1:.4f})')

# Final evaluation with all thresholds
adjusted_probs = all_probs.copy()
for c in range(NUM_CLASSES):
    adjusted_probs[:, c] = adjusted_probs[:, c] / thresholds[c]
final_preds = adjusted_probs.argmax(axis=1)
final_f1 = f1_score(all_labels_th, final_preds, average='macro', zero_division=0)
print(f'\nOptimized thresholds F1: {final_f1:.4f} (vs unoptimized best: {best_f1:.4f})')

# Save thresholds
thresholds_dict = {CLASS_NAMES[i]: float(thresholds[i]) for i in range(NUM_CLASSES)}
thresholds_path = os.path.join(MODELS_PATH, 'thresholds_V6.0.json')
with open(thresholds_path, 'w') as f:
    json.dump(thresholds_dict, f, indent=2)
print(f'Thresholds saved to {thresholds_path}')


state = {
    'version': VERSION, 'phase': 'phase2',
    'best_epoch': best_epoch, 'best_f1': float(best_f1),
    'swa_val_f1': float(swa_val_f1),
    'optimized_f1': float(final_f1),
    'thresholds': thresholds_dict,
    'total_epochs_trained': EPOCH_OFFSET + len(history),
    'phase2_epochs': len(history),
    'training_time_minutes': elapsed / 60,
}
state_path = os.path.join(RESULTS_PATH, 'phase2_state.json')
with open(state_path, 'w') as f:
    json.dump(state, f, indent=2)
print(f'✅ saved -> {state_path}')
print(f'✅ Best F1: {best_f1:.4f} at epoch {best_epoch}')

# Save detailed JSON training log with timestamp
log_dir = os.path.join(RESULTS_PATH, 'training_logs')
os.makedirs(log_dir, exist_ok=True)
timestamp = time.strftime('%Y%m%d_%H%M%S')
log_path = os.path.join(log_dir, f'{timestamp}_phase2.json')
with open(log_path, 'w') as f:
    json.dump(history, f, indent=2)
print(f'saved -> {log_path}')


# ────────────────────────────────────────────────────────────
# ## CELL 12 — Training Metrics Plot & Final Summary


# ── Cell 29 ───────────────────────────────────────
# --- Training Plot ---
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
epochs_range = [h['epoch'] for h in history]

axes[0].plot(epochs_range, [h['train_loss'] for h in history], 'b-', label='Train', lw=2)
axes[0].plot(epochs_range, [h['val_loss'] for h in history], 'r-', label='Val', lw=2)
if best_epoch in epochs_range:
    axes[0].axvline(x=best_epoch, color='g', ls='--', alpha=0.7, label=f'Best (ep {best_epoch})')
swa_epoch = EPOCH_OFFSET + SWA_START_EPOCH
if swa_epoch in epochs_range:
    axes[0].axvline(x=swa_epoch, color='purple', ls=':', alpha=0.7, label='SWA start')
axes[0].set_xlabel('Epoch'); axes[0].set_ylabel('Loss'); axes[0].set_title('Loss'); axes[0].legend(); axes[0].grid(True, alpha=0.3)

axes[1].plot(epochs_range, [h['train_f1'] for h in history], 'b-', label='Train F1', lw=2)
axes[1].plot(epochs_range, [h['val_f1'] for h in history], 'r-', label='Val F1', lw=2)
if best_epoch in epochs_range:
    axes[1].axvline(x=best_epoch, color='g', ls='--', alpha=0.7)
axes[1].axhline(y=best_f1, color='g', ls=':', alpha=0.5, label=f'Best={best_f1:.4f}')
axes[1].set_xlabel('Epoch'); axes[1].set_ylabel('Macro F1'); axes[1].set_title('F1 Score'); axes[1].legend(); axes[1].grid(True, alpha=0.3)

axes[2].plot(epochs_range, [h['lr'] for h in history], 'g-', lw=2)
axes[2].set_xlabel('Epoch'); axes[2].set_ylabel('LR'); axes[2].set_title('Learning Rate'); axes[2].set_yscale('log'); axes[2].grid(True, alpha=0.3)

plt.suptitle(f'MedAssist V6.0 Phase 2 (Best F1={best_f1:.4f} @ Epoch {best_epoch})', fontsize=14, fontweight='bold')
plt.tight_layout()
plot_path = os.path.join(RESULTS_PATH, 'phase2_training_metrics_V6.0.png')
plt.savefig(plot_path, dpi=150, bbox_inches='tight'); plt.show()
print(f'saved -> {plot_path}')




print('\n' + '=' * 60)
print('  PHASE 2 TRAINING COMPLETE')
print('=' * 60)
print(f'  Version:          {VERSION}')
print(f'  Best F1:          {best_f1:.4f} at epoch {best_epoch}')
print(f'  SWA F1:           {swa_val_f1:.4f}')
print(f'  Optimized F1:     {final_f1:.4f}')
print(f'  Thresholds:       {thresholds_dict}')
print(f'  Time:             {elapsed/60:.1f} minutes')
print(f'\n  Saved:')
print(f'    - best_model_V6.0_phase2_f1_{best_f1:.4f}.pth')
print(f'    - swa_model_V6.0.pth')
print(f'    - phase2_history.csv')
print(f'    - phase2_state.json')
print(f'\n  -> Ready for 05_evaluation_V6.0')
print('=' * 60)

gc.collect()
torch.cuda.empty_cache()
