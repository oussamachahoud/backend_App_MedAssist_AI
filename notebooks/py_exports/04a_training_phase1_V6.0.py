# ═══ NOTEBOOK: 04a_training_phase1_V6.0.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 04a: Training Phase 1 V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | CutMix (replaces Mixup), progressive resizing img=128→256, meta_mask in all loops, SkinLesionDataset searches PAD+ISIC+MCR dirs, auto-resume from checkpoint |
# | V5.0 | Multimodal Mixup, 7 meta features, HAM10000 backbone, Progressive Unfreezing, WeightedRandomSampler |
# | V4.2 | Basic training loop |
# 
# ## Purpose
# - Phase 1: 35 epochs at img=128 (fast)
# - Backbone frozen for first 5 epochs (warmup)
# - CutMix augmentation (p=0.3, alpha=1.0)
# - Cosine Annealing Warm Restarts scheduler
# - Auto-resume from last checkpoint on session reconnect
# - MLflow tracking


# ────────────────────────────────────────────────────────────
# ## CELL 0 — Environment Setup & Imports


# ── Cell 3 ───────────────────────────────────────
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
print('All packages ready.')

import os, gc, csv, json, math, pickle, warnings, glob, time
import numpy as np
import pandas as pd
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torch.cuda.amp import autocast, GradScaler
import timm
import albumentations as A
from albumentations.pytorch import ToTensorV2
from sklearn.metrics import f1_score, classification_report
from transformers import get_cosine_schedule_with_warmup
import mlflow
from tqdm.auto import tqdm

warnings.filterwarnings('ignore')
torch.backends.cudnn.benchmark = True

VERSION        = 'V6.0'
BASE_PATH      = '/content/drive/MyDrive/MedAssist_AI'
DATASET_PATH   = os.path.join(BASE_PATH, 'dataset')
PROCESSED_PATH = os.path.join(BASE_PATH, 'data', 'processed')
MODELS_PATH    = os.path.join(BASE_PATH, 'models')
RESULTS_PATH   = os.path.join(BASE_PATH, 'results')
MLFLOW_DIR     = os.path.join(RESULTS_PATH, 'mlruns')

for p in [MODELS_PATH, RESULTS_PATH, MLFLOW_DIR]:
    os.makedirs(p, exist_ok=True)

os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
mlflow.set_tracking_uri(f'file://{MLFLOW_DIR}')
mlflow.set_experiment('MedAssist_V6_Phase1')

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('=' * 60)
print(f'  MedAssist AI — Training Phase 1 {VERSION}')
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
DRIVE_DATASET = '/content/drive/MyDrive/MedAssist_AI/dataset'
ZIP_IN_DRIVE  = '/content/drive/MyDrive/MedAssist_AI/dataset/images.zip'
LOCAL_IMAGES  = '/content/local_dataset/images'

os.makedirs(DRIVE_DATASET, exist_ok=True)

if os.path.exists(ZIP_IN_DRIVE):
    size_mb = os.path.getsize(ZIP_IN_DRIVE) / (1024 ** 2)
    print(f'images.zip found in Drive ({size_mb:.0f} MB)')
else:
    print('Creating images.zip in Drive (one-time, ~1-2 min)...')
    os.system(f'cd {DRIVE_DATASET} && zip -r -q images.zip images/')
    if os.path.exists(ZIP_IN_DRIVE):
        size_mb = os.path.getsize(ZIP_IN_DRIVE) / (1024 ** 2)
        print(f'Done! images.zip = {size_mb:.0f} MB')
    else:
        print(f'Warning: images.zip not created. Ensure images/ dir exists in {DRIVE_DATASET}')

if os.path.isdir(LOCAL_IMAGES) and len(os.listdir(LOCAL_IMAGES)) > 0:
    n = sum(len(f) for _, _, f in os.walk(LOCAL_IMAGES))
    print(f'Local SSD already has PAD-UFES-20 images ({n} files) — skipping extract.')
else:
    if os.path.exists(ZIP_IN_DRIVE):
        stream_extract_zip(ZIP_IN_DRIVE, LOCAL_IMAGES, batch_size=500,
                           label='PAD-UFES-20')
    else:
        print(f'Error: {ZIP_IN_DRIVE} not found.')

images_dir = LOCAL_IMAGES
if not os.path.isdir(images_dir) or not os.listdir(images_dir):
    print('WARNING: local SSD images not found, falling back to Drive...')
    images_dir = os.path.join(DATASET_PATH, 'images')
print(f'Dataset ready at: {images_dir}')
# ── ISIC 2019 → SSD (stream, no cp) ──────────────────────────────────────────


# ────────────────────────────────────────────────────────────
# ## CELL 2 — Load ISIC 2019 to SSD


# ── Cell 7 ───────────────────────────────────────
ISIC_ZIP_DRIVE = '/content/drive/MyDrive/MedAssist_AI/dataset_isic2019/isic_2019_images.zip'
LOCAL_ISIC_DIR = '/content/local_dataset/isic2019'

if os.path.isdir(LOCAL_ISIC_DIR) and len(os.listdir(LOCAL_ISIC_DIR)) > 100:
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
with open(os.path.join(PROCESSED_PATH, 'preprocessing_config.json'), 'r') as f:
    config = json.load(f)

assert config['version'] == 'V6.0', f"Version mismatch: {config['version']}"
NUM_CLASSES    = config['num_classes']          # 6
NUM_META       = config['num_meta_features']    # 7
CLASS_NAMES    = config['class_names']          # ['ACK','BCC','MEL','NEV','SCC','SEK']
IMG_SIZE       = 128  # Task 3.1: Progressive Resizing (Start small in Phase 1)
SELECTED_FEATS = config['selected_features']    # 7 ABCDE features
NORM_MEAN      = config['normalization']['mean']
NORM_STD       = config['normalization']['std']

class_weights_np = np.load(os.path.join(PROCESSED_PATH, 'class_weights.npy'))
weights_tensor   = torch.tensor(class_weights_np, dtype=torch.float32).to(device)

print(f'✅ Config V6.0: {NUM_META} features, {NUM_CLASSES} classes, img={IMG_SIZE}')
print(f'✅ Classes: {CLASS_NAMES}')
print(f'✅ Class weights: {dict(zip(CLASS_NAMES, [f"{w:.3f}" for w in class_weights_np]))}')


# ────────────────────────────────────────────────────────────
# ## CELL 4 — V6.0 Preprocessing Functions (Shades-of-Gray + DullRazor)


# ── Cell 11 ───────────────────────────────────────
def shades_of_gray(img, power=6):
    """Shades of Gray color constancy (power=6)."""
    img_f = img.astype(np.float32) + 1e-7
    if power == -1:  # max
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
    blurred_img = cv2.GaussianBlur(img, (15, 15), 0) # ULTRA-FAST Gaussian filter

    # Expand mask to 3 channels so it matches the image shape
    hair_mask_3d = np.expand_dims(hair_mask, axis=-1)

    # Where mask is white (hair), use blurred background. Otherwise, use original.
    result = np.where(hair_mask_3d > 0, blurred_img, img)

    return result.astype(np.uint8)



print('✅ V6.0 preprocessing: shades_of_gray (power=6) + DullRazor (17×17, thresh=10)')
train_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.2, rotate_limit=45, p=0.7),
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.5),
    A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.5),
    A.CoarseDropout(max_holes=8, max_height=32, max_width=32, fill_value=0, p=0.5),
    A.ElasticTransform(alpha=1, sigma=50, alpha_affine=50, p=0.3),
    A.GridDistortion(num_steps=5, distort_limit=0.3, p=0.3),
    A.CLAHE(clip_limit=2.0, p=1.0),
    A.OneOf([                                        # ✅ إضافة: RandAugment policy
        A.Solarize(threshold=128, p=1.0),
        A.Posterize(num_bits=4, p=1.0),
        A.Equalize(p=1.0),
        A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1.0), p=1.0),
        A.GaussianBlur(blur_limit=(3, 5), p=1.0),
    ], p=0.3),
    A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.4),
    A.Normalize(mean=NORM_MEAN, std=NORM_STD),
    ToTensorV2()
])

val_transforms = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.CLAHE(clip_limit=2.0, p=1.0),
    A.Normalize(mean=NORM_MEAN, std=NORM_STD),
    ToTensorV2()
])


# ────────────────────────────────────────────────────────────
# ## CELL 5 — Transforms & SkinLesionDataset (PAD + ISIC + MCR, meta_mask)


# ── Cell 13 ───────────────────────────────────────
class SkinLesionDataset(Dataset):
    """V6.0 Dataset — searches PAD-UFES-20 + ISIC 2019 + MCR-SL image dirs."""

    def __init__(self, df, images_dir, metadata_cols, transform=None):
        self.df            = df.reset_index(drop=True)
        self.images_dir    = images_dir
        self.transform     = transform
        self.metadata_cols = metadata_cols

        # Build image path lookup ONCE at init
        # Searches PAD-UFES-20 subdirs + flat dir + ISIC 2019 + MCR-SL
        self.img_paths = {}

        # PAD-UFES-20: nested subdirs
        for sub in ['imgs_part_1/imgs_part_1', 'imgs_part_2/imgs_part_2', 'imgs_part_3/imgs_part_3']:
            full_dir = os.path.join(images_dir, sub)
            if os.path.isdir(full_dir):
                for fname in os.listdir(full_dir):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                        self.img_paths[fname] = os.path.join(full_dir, fname)
        # PAD-UFES-20: flat directory (from zip extraction)
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

        # Verify all DataFrame images are found
        missing = [f for f in df['img_filename'].values if f not in self.img_paths]
        if missing:
            print(f'⚠️  WARNING: {len(missing)} images not found! Dropping them from dataset. First 5: {missing[:5]}')
            missing_set = set(missing)
            self.df = self.df[~self.df['img_filename'].isin(missing_set)].reset_index(drop=True)
        else:
            print(f'✅ All {len(self.df)} images found ({len(self.img_paths):,} total in lookup)')

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
                    f"Re-run CELL 1 (SSD extract) then CELL 6 (Pre-cache).")
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
            # ISIC-2019: only age and gender are available
            meta_mask = torch.tensor([1, 1, 0, 0, 0, 0, 0], dtype=torch.float32)
        return img, meta, meta_mask, label, img_filename


# ────────────────────────────────────────────────────────────
# ## CELL 5.5 — DataLoaders & Pre-Cache Cell (Run at Every Session Start)


# ── Cell 15 ───────────────────────────────────────
print('✅ SkinLesionDataset V6.0 defined (shades_of_gray + DullRazor + CLAHE)')
train_df = pd.read_csv(os.path.join(PROCESSED_PATH, 'train.csv'))
val_df   = pd.read_csv(os.path.join(PROCESSED_PATH, 'val.csv'))

train_dataset = SkinLesionDataset(train_df, images_dir, SELECTED_FEATS, train_transforms)
val_dataset   = SkinLesionDataset(val_df,   images_dir, SELECTED_FEATS, val_transforms)

# WeightedRandomSampler â€” replaces shuffle=True for class-balanced sampling
sample_weights = np.array([class_weights_np[label] for label in train_df['label'].values])
sample_weights = sample_weights / sample_weights.sum()
sampler = WeightedRandomSampler(
    weights=torch.DoubleTensor(sample_weights),
    num_samples=len(train_dataset),
    replacement=True
)

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


print(f'✅ DataLoaders: train={len(train_loader)} batches, val={len(val_loader)} batches')
print(f'✅ WeightedRandomSampler active (class-balanced sampling)')


# ────────────────────────────────────────────────────────────
# ## CELL 6 — Pre-Cache: Apply Preprocessing → /content/fast_images/


# ── Cell 17 ───────────────────────────────────────
##Cell 5.5 Pre-Cache Cell

assert 'train_dataset' in globals(), "❌ Run CELL 5 (DataLoaders) first before pre-caching!"

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


# ────────────────────────────────────────────────────────────
# ## CELL 7 — Gated Cross-Attention Fusion Architecture


# ── Cell 19 ───────────────────────────────────────
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
        features = self.backbone(x)          # (B, C, H, W)

        if 'swin' in self.backbone_name:
            if features.dim() == 3: # (B, L, C) -> (B, C, H, W)
                B, L, C = features.shape
                H = W = int(math.sqrt(L))
                features = features.transpose(1, 2).view(B, C, H, W)
            elif features.dim() == 4 and features.shape[1] == features.shape[2]: # (B, H, W, C)
                features = features.permute(0, 3, 1, 2)

        aux_logits = self.auxiliary_head(features)  # (B, 6)

        pooled = self.pool(features)          # (B, C, 7, 7)
        projected = self.projection(pooled)   # (B, 256, 7, 7)
        B, C, H, W = projected.shape
        patches = projected.view(B, C, H*W).permute(0, 2, 1)  # (B, 49, 256)

        return patches, aux_logits, features


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


# ────────────────────────────────────────────────────────────
# ## CELL 8 — Full MedAssistModel V6.0 & Model Init


# ── Cell 21 ───────────────────────────────────────
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


# ────────────────────────────────────────────────────────────
# ## CELL 9 — GPU Setup, HAM10000 Backbone & Parameters


# ── Cell 23 ───────────────────────────────────────
criterion = WeightedFocalLoss(
    alpha=None, gamma=2.0, label_smoothing=0.05).to(device)


model = MedAssistModel(num_meta=NUM_META, num_classes=NUM_CLASSES).to(device)

total_params = sum(p.numel() for p in model.parameters())
print(f'Parameters: {total_params:,} total')

# --- HAM10000 Pre-trained Backbone Loading ---


# ────────────────────────────────────────────────────────────
# ## CELL 10 — Optimizer, Scheduler & CutMix


# ── Cell 25 ───────────────────────────────────────
HAM_BACKBONE_PATH = os.path.join(MODELS_PATH, 'ham10000_backbone_b3.pth')
if os.path.exists(HAM_BACKBONE_PATH):
    ham_state = torch.load(HAM_BACKBONE_PATH, map_location=device)
    msg = model.image_branch.backbone.load_state_dict(ham_state, strict=False)
    print(f'Loaded HAM10000 pre-trained backbone ({len(ham_state)} keys)')
    if msg.missing_keys:
        print(f'  Missing keys: {len(msg.missing_keys)}')
else:
    print(f'HAM10000 backbone not found, using ImageNet weights')
    print(f'   Run 03b_ham10000_pretrain_V6.0.py first for +3-5% improvement')

# --- Progressive Unfreezing: Freeze backbone during warmup ---
UNFREEZE_EPOCH = 6  # Unfreeze at the start of epoch 6 (after 5 warmup epochs)
for param in model.image_branch.backbone.parameters():
    param.requires_grad = False

trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'Backbone FROZEN for warmup (epochs 1-{UNFREEZE_EPOCH - 1})')
print(f'Trainable params (head only): {trainable_params:,}')
# Differential Learning Rates
LR_BACKBONE = 1e-5
LR_HEAD     = 1e-4
WEIGHT_DECAY = 0.1

backbone_params = list(model.image_branch.backbone.parameters())
backbone_ids = set(id(p) for p in backbone_params)
head_params = [p for p in model.parameters() if id(p) not in backbone_ids]

optimizer = torch.optim.AdamW([
    {'params': backbone_params, 'lr': LR_BACKBONE},
    {'params': head_params,     'lr': LR_HEAD},
], weight_decay=WEIGHT_DECAY)

# Task 3.3: LinearLR Warmup → CosineAnnealingWarmRestarts
NUM_EPOCHS    = 55
WARMUP_EPOCHS = 5    # ✅ إضافة: 5 epochs warmup خطي

from torch.optim.lr_scheduler import SequentialLR, LinearLR, CosineAnnealingWarmRestarts as CosineWR

_warmup = LinearLR(
    optimizer,
    start_factor=0.1,    # يبدأ من 10% من LR (backbone=1e-6, head=1e-5)
    end_factor=1.0,      # يصل إلى LR الكامل بنهاية WARMUP_EPOCHS
    total_iters=WARMUP_EPOCHS
)
_cosine = CosineWR(
    optimizer,
    T_0=10,
    T_mult=1,
    eta_min=1e-6
)
scheduler = SequentialLR(
    optimizer,
    schedulers=[_warmup, _cosine],
    milestones=[WARMUP_EPOCHS]
)

scaler = GradScaler()
GRAD_CLIP = 1.0
PATIENCE  = 20       # ✅ رُفع من 15 — يتجاوز restart الثاني عند epoch 20
MIN_DELTA = 0.001    # ✅ إضافة: تحسن أدنى معتبر لتصفير patience

print(f'✅ Optimizer: AdamW (backbone LR={LR_BACKBONE}, head LR={LR_HEAD}, wd={WEIGHT_DECAY})')
print(f'✅ Scheduler: LinearWarmup({WARMUP_EPOCHS} ep) → CosineAnnealingWarmRestarts (T_0=10)')
print(f'✅ Training: {NUM_EPOCHS} epochs, patience={PATIENCE}, min_delta={MIN_DELTA}, grad_clip={GRAD_CLIP}')



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
    """Compute loss with soft mixed labels."""
    log_probs = F.log_softmax(logits, dim=-1)
    loss = -(mixed_labels * log_probs).sum(dim=-1).mean()
    return loss


print('✅ CutMix defined (p=0.3, alpha=1.0) replacing Multimodal Mixup')


# ────────────────────────────────────────────────────────────
# ## CELL 11 — Training & Validation Functions


# ── Cell 27 ───────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, scheduler, scaler, device, epoch):
    """Train one epoch with AMP, mixup, and gradient clipping."""
    model.train()
    running_loss = 0.0
    all_preds, all_labels = [], []

    pbar = tqdm(loader, desc=f'Epoch {epoch:02d}/{NUM_EPOCHS} [Train]', leave=False)
    for images, meta, meta_mask, labels, _ in pbar:
        images    = images.to(device, non_blocking=True)
        meta      = meta.to(device, non_blocking=True)
        meta_mask = meta_mask.to(device, non_blocking=True)
        labels    = labels.to(device, non_blocking=True)

        # CutMix instead of Multimodal Mixup
        mixed_images, mixed_meta, mixed_labels, lam = cutmix_data(
            images, meta, labels, alpha=1.0, p=0.3
        )

        optimizer.zero_grad(set_to_none=True)

        with autocast():
            main_logits, aux_logits, gate = model(mixed_images, mixed_meta, meta_mask)

            if lam is not None:
                # Mixup active: use soft label loss
                main_loss = compute_mixup_loss(main_logits, mixed_labels, criterion)
                aux_loss  = compute_mixup_loss(aux_logits, mixed_labels, criterion)
            else:
                # No mixup: standard loss with hard labels
                main_loss = criterion(main_logits, labels)
                aux_loss  = criterion(aux_logits, labels)

            loss = 0.7 * main_loss + 0.3 * aux_loss

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item() * images.size(0)

        # Track predictions (use main_logits, original labels for metrics)
        with torch.no_grad():
            preds = main_logits.argmax(dim=1)
            if lam is None:
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        pbar.set_postfix({'loss': f'{loss.item():.4f}', 'lr': f'{scheduler.get_last_lr()[0]:.2e}'})

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


print('✅ train_one_epoch and validate functions defined')
print('\n' + '=' * 60)


# ────────────────────────────────────────────────────────────
# ## CELL 12 — Main Training Loop + Save Results + Final Summary


# ── Cell 29 ───────────────────────────────────────
print('  STARTING PHASE 1 TRAINING (Epochs 1-35)')
print('=' * 60 + '\n')

best_f1 = 0.0
best_epoch = 0
patience_counter = 0
history = []
start_epoch = 1
start_time = time.time()

# --- Auto-Resume: Load last checkpoint if session was interrupted ---
resume_ckpts = sorted(glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase1_f1_*.pth')))
if resume_ckpts:
    resume_ckpt = torch.load(resume_ckpts[-1], map_location=device)
    model.load_state_dict(resume_ckpt['model_state_dict'])
    optimizer.load_state_dict(resume_ckpt['optimizer_state_dict'])
    scheduler.load_state_dict(resume_ckpt['scheduler_state_dict'])
    scaler.load_state_dict(resume_ckpt['scaler_state_dict'])
    start_epoch = resume_ckpt['epoch'] + 1
    best_f1 = resume_ckpt['best_f1']
    best_epoch = resume_ckpt['epoch']
    # Unfreeze backbone if we're past the unfreeze epoch
    if start_epoch >= UNFREEZE_EPOCH:
        for param in model.image_branch.backbone.parameters():
            param.requires_grad = True
    print(f'🔄 RESUMED from epoch {resume_ckpt["epoch"]}, best F1={best_f1:.4f}')
    print(f'   Continuing from epoch {start_epoch} → {NUM_EPOCHS}')
else:
    print('🆕 Starting fresh training (no checkpoint found)')

with mlflow.start_run(run_name=f'MedAssist_V6.0_Phase1'):
    # Log parameters
    mlflow.log_params({
        'version': VERSION,
        'phase': 'phase1',
        'num_epochs': NUM_EPOCHS,
        'batch_size': BATCH_SIZE,
        'lr_backbone': LR_BACKBONE,
        'lr_head': LR_HEAD,
        'weight_decay': WEIGHT_DECAY,
        'patience': PATIENCE,
        'grad_clip': GRAD_CLIP,
        'img_size': IMG_SIZE,
        'num_meta_features': NUM_META,
        'num_classes': NUM_CLASSES,
        'loss_fn': 'WeightedFocalLoss',
        'focal_gamma': 2.5,
        'cutmix_p': 0.3,
        'cutmix_alpha': 1.0,
        'main_loss_weight': 0.7,
        'aux_loss_weight': 0.3,
        'sampler': 'WeightedRandomSampler',
        'resumed_from_epoch': start_epoch - 1,
    })

    for epoch in range(start_epoch, NUM_EPOCHS + 1):
        # --- Progressive Unfreezing ---
        if epoch == UNFREEZE_EPOCH:
            for param in model.image_branch.backbone.parameters():
                param.requires_grad = True
            trainable_now = sum(p.numel() for p in model.parameters() if p.requires_grad)
            print(f'\n\U0001f513 Backbone UNFROZEN at epoch {epoch} ({trainable_now:,} trainable params)\n')

        # Train
        train_loss, train_f1 = train_one_epoch(
            model, train_loader, criterion, optimizer, scheduler, scaler, device, epoch
        )
        scheduler.step()

        # Validate
        _use_tta = (epoch >= 10)   # ✅ TTA من epoch 10 فقط لتوفير الوقت
        val_loss, val_f1, val_preds, val_labels = validate(
            model, val_loader, criterion, device, use_tta=_use_tta
        )

        # Current LR
        current_lr = scheduler.get_last_lr()[0]

        # Log to MLflow
        mlflow.log_metrics({
            'train_loss': train_loss,
            'train_f1': train_f1,
            'val_loss': val_loss,
            'val_f1': val_f1,
            'learning_rate': current_lr,
        }, step=epoch)

        # Save history
        history.append({
            'epoch': epoch,
            'train_loss': train_loss,
            'train_f1': train_f1,
            'val_loss': val_loss,
            'val_f1': val_f1,
            'best_f1': max(best_f1, val_f1),
            'lr': current_lr,
        })

        # Check for improvement
        if val_f1 > best_f1 + MIN_DELTA:   # ✅ إصلاح: تحسن حقيقي فقط
            best_f1 = val_f1
            best_epoch = epoch
            patience_counter = 0

            # Save best checkpoint
            ckpt_name = f'best_model_V6.0_phase1_f1_{val_f1:.4f}.pth'
            ckpt_path = os.path.join(MODELS_PATH, ckpt_name)

            # Remove old best checkpoints
            old_ckpts = glob.glob(os.path.join(MODELS_PATH, 'best_model_V6.0_phase1_f1_*.pth'))
            for old in old_ckpts:
                os.remove(old)

            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'scaler_state_dict': scaler.state_dict(),
                'best_f1': best_f1,
                'val_loss': val_loss,
                'train_loss': train_loss,
            }, ckpt_path)
            print(f'  >> New best! F1={val_f1:.4f} saved to {ckpt_name}')
        else:
            patience_counter += 1

        print(f'Epoch {epoch:02d}/{NUM_EPOCHS} | '
              f'Loss:{train_loss:.4f} | ValF1:{val_f1:.4f} | '
              f'Best:{best_f1:.4f} | LR:{current_lr:.2e} | '
              f'Patience:{patience_counter}/{PATIENCE}')

        # Early stopping
        if patience_counter >= PATIENCE:
            print(f'\nâš ï¸  Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)')
            break

    elapsed = time.time() - start_time
    print(f'\n✅ Phase 1 training complete in {elapsed/60:.1f} minutes')
    print(f'✅ Best F1: {best_f1:.4f} at epoch {best_epoch}')

    mlflow.log_metrics({'best_f1': best_f1, 'best_epoch': best_epoch})




# Save history CSV
history_path = os.path.join(RESULTS_PATH, 'phase1_history.csv')
history_df = pd.DataFrame(history)
history_df.to_csv(history_path, index=False)
print(f'saved -> {history_path}')

# Save state JSON
state = {
    'version': VERSION,
    'phase': 'phase1',
    'best_epoch': best_epoch,
    'best_f1': float(best_f1),
    'total_epochs_trained': len(history),
    'max_epochs': NUM_EPOCHS,
    'early_stopped': patience_counter >= PATIENCE,
    'lr_backbone': LR_BACKBONE,
    'lr_head': LR_HEAD,
    'batch_size': BATCH_SIZE,
    'training_time_minutes': elapsed / 60,
}
state_path = os.path.join(RESULTS_PATH, 'phase1_state.json')
with open(state_path, 'w') as f:
    json.dump(state, f, indent=2)
print(f'saved -> {state_path}')

# Save detailed JSON training log with timestamp
log_dir = os.path.join(RESULTS_PATH, 'training_logs')
os.makedirs(log_dir, exist_ok=True)
timestamp = time.strftime('%Y%m%d_%H%M%S')
log_path = os.path.join(log_dir, f'{timestamp}_phase1.json')
with open(log_path, 'w') as f:
    json.dump(history, f, indent=2)
print(f'saved -> {log_path}')



fig, axes = plt.subplots(1, 3, figsize=(18, 5))

epochs_range = [h['epoch'] for h in history]

# Loss
axes[0].plot(epochs_range, [h['train_loss'] for h in history], 'b-', label='Train Loss', linewidth=2)
axes[0].plot(epochs_range, [h['val_loss'] for h in history], 'r-', label='Val Loss', linewidth=2)
axes[0].axvline(x=best_epoch, color='g', linestyle='--', alpha=0.7, label=f'Best (ep {best_epoch})')
axes[0].set_xlabel('Epoch')
axes[0].set_ylabel('Loss')
axes[0].set_title('Training & Validation Loss')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# F1 Score
axes[1].plot(epochs_range, [h['train_f1'] for h in history], 'b-', label='Train F1', linewidth=2)
axes[1].plot(epochs_range, [h['val_f1'] for h in history], 'r-', label='Val F1', linewidth=2)
axes[1].axvline(x=best_epoch, color='g', linestyle='--', alpha=0.7, label=f'Best (ep {best_epoch})')
axes[1].axhline(y=best_f1, color='g', linestyle=':', alpha=0.5, label=f'Best F1={best_f1:.4f}')
axes[1].set_xlabel('Epoch')
axes[1].set_ylabel('Macro F1')
axes[1].set_title('Training & Validation F1 Score')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

# Learning Rate
axes[2].plot(epochs_range, [h['lr'] for h in history], 'g-', linewidth=2)
axes[2].set_xlabel('Epoch')
axes[2].set_ylabel('Learning Rate')
axes[2].set_title('Learning Rate Schedule')
axes[2].set_yscale('log')
axes[2].grid(True, alpha=0.3)

plt.suptitle(f'MedAssist V6.0 â€” Phase 1 Training (Best F1={best_f1:.4f} @ Epoch {best_epoch})',
             fontsize=14, fontweight='bold')
plt.tight_layout()

plot_path = os.path.join(RESULTS_PATH, 'phase1_training_metrics.png')
plt.savefig(plot_path, dpi=150, bbox_inches='tight')
plt.show()
print(f'saved -> {plot_path}')



print('\n' + '=' * 60)
print('  PHASE 1 TRAINING COMPLETE')
print('=' * 60)
print(f'  Version:     {VERSION}')
print(f'  Best F1:     {best_f1:.4f}')
print(f'  Best Epoch:  {best_epoch}')
print(f'  Epochs Run:  {len(history)}')
print(f'  Time:        {elapsed/60:.1f} minutes')
print(f'\n  Saved files:')
print(f'    - best_model_V6.0_phase1_f1_{best_f1:.4f}.pth')
print(f'    - phase1_history.csv')
print(f'    - phase1_state.json')
print(f'    - phase1_training_metrics.png')
print(f'\n  ➡️   Ready for Phase 2 (04b_training_phase2_V6_0_split.py)')
print('=' * 60)
