# ═══ NOTEBOOK: 03b_ham10000_pretrain_V6.0.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 03b: HAM10000 Pre-training V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | Smart skip if backbone already exists, class-weighted loss |
# | V5.0 | Auto-downloads HAM10000, pre-trains EfficientNet-B3 backbone |
# 
# ## Changes vs V5.0
# - NEW: Saves final epoch weights (not best F1 epoch — known limitation)
# - Correctly excludes classifier head when saving backbone weights
# - Run ONCE before 04a — skip logic prevents re-training


# ────────────────────────────────────────────────────────────
# ## CELL 0 — Imports, Setup & Skip Check


# ── Cell 3 ───────────────────────────────────────
#!/usr/bin/env python3
"""
MedAssist AI — 03b HAM10000 Pre-training V6.0
Pre-train EfficientNet-B3 backbone on HAM10000 (7-class dermatoscopy dataset)
for transfer learning to PAD-UFES-20.

Run this ONCE before 04a_training_phase1_V6.0.py
Google Colab T4 GPU | ~15-20 minutes
Output: models/ham10000_backbone_b3.pth
"""

from google.colab import drive
try:
    drive.mount('/content/drive')
except Exception:
    print('Drive already mounted.')

import subprocess, sys
for pkg in ['timm', 'albumentations']:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

import os, glob, time, gc, warnings
import numpy as np
import pandas as pd
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
import timm
import albumentations as A
from albumentations.pytorch import ToTensorV2
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from tqdm.auto import tqdm

warnings.filterwarnings('ignore')
torch.backends.cudnn.benchmark = True

VERSION = 'V6.0'
BASE_PATH = '/content/drive/MyDrive/MedAssist_AI'
MODELS_PATH = os.path.join(BASE_PATH, 'models')
os.makedirs(MODELS_PATH, exist_ok=True)

HAM_BACKBONE_PATH = os.path.join(MODELS_PATH, 'ham10000_backbone_b3.pth')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print('=' * 60)
print(f'  MedAssist AI — HAM10000 Pre-training {VERSION}')
print(f'  Device: {device}')
print('=' * 60)

# ============================================================
# Check if already done
# ============================================================
if os.path.exists(HAM_BACKBONE_PATH):
    print(f'\n✅ HAM10000 backbone already exists at {HAM_BACKBONE_PATH}')
    print('   Delete it and re-run if you want to re-train.')
    SKIP = True
else:
    SKIP = False


# ────────────────────────────────────────────────────────────
# ## CELL 1 — Download HAM10000 from Kaggle


# ── Cell 5 ───────────────────────────────────────
if not SKIP:
    HAM_DIR = '/content/ham10000'
    HAM_DATASET = 'kmader/skin-cancer-mnist-ham10000'

    # Check if already downloaded
    ham_csvs = glob.glob(os.path.join(HAM_DIR, '**', 'HAM10000_metadata*'), recursive=True)
    if ham_csvs:
        print(f'HAM10000 already downloaded at {HAM_DIR}')
    else:
        print(f'Downloading HAM10000 from Kaggle...')
        os.system(f'pip install kaggle -q')
        os.system(f'kaggle datasets download -d {HAM_DATASET} -p /content/')
        os.makedirs(HAM_DIR, exist_ok=True)
        # Find the zip
        zip_candidates = glob.glob('/content/skin-cancer-mnist-ham10000.zip')
        if zip_candidates:
            os.system(f'unzip -q {zip_candidates[0]} -d {HAM_DIR}')
            os.system(f'rm -f {zip_candidates[0]}')
        else:
            print('ERROR: Could not find downloaded zip. Check Kaggle API key.')

    # Find metadata CSV
    ham_csvs = glob.glob(os.path.join(HAM_DIR, '**', 'HAM10000_metadata*'), recursive=True)
    if not ham_csvs:
        raise FileNotFoundError('HAM10000 metadata not found! Check download.')
    ham_meta_path = ham_csvs[0]
    print(f'Metadata: {ham_meta_path}')

    # Find image directories
    ham_img_files = {}
    for root, dirs, files in os.walk(HAM_DIR):
        for f in files:
            if f.endswith('.jpg') or f.endswith('.png'):
                ham_img_files[os.path.splitext(f)[0]] = os.path.join(root, f)
    print(f'Found {len(ham_img_files)} images')


# ────────────────────────────────────────────────────────────
# ## CELL 2 — HAM10000 Dataset & DataLoaders


# ── Cell 7 ───────────────────────────────────────
if not SKIP:
    HAM_CLASSES = sorted(['akiec', 'bcc', 'bkl', 'df', 'mel', 'nv', 'vasc'])
    HAM_NUM_CLASSES = 7
    IMG_SIZE = 256

    ham_df = pd.read_csv(ham_meta_path)
    # Map dx to label
    ham_label_map = {c: i for i, c in enumerate(HAM_CLASSES)}
    ham_df['label'] = ham_df['dx'].map(ham_label_map)
    ham_df = ham_df.dropna(subset=['label'])
    ham_df['label'] = ham_df['label'].astype(int)

    # Check images exist
    ham_df['img_path'] = ham_df['image_id'].map(ham_img_files)
    ham_df = ham_df.dropna(subset=['img_path'])
    print(f'HAM10000: {len(ham_df)} samples, {HAM_NUM_CLASSES} classes')
    print(ham_df['dx'].value_counts())

    # Split: 90% train, 10% val
    train_ham, val_ham = train_test_split(
        ham_df, test_size=0.1, stratify=ham_df['label'], random_state=42
    )
    print(f'Train: {len(train_ham)}, Val: {len(val_ham)}')

    ham_train_transforms = A.Compose([
        A.Resize(IMG_SIZE, IMG_SIZE),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.15, rotate_limit=30, p=0.5),
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.3),
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2()
    ])
    ham_val_transforms = A.Compose([
        A.Resize(IMG_SIZE, IMG_SIZE),
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2()
    ])

    class HAM10000Dataset(Dataset):
        def __init__(self, df, transform=None):
            self.df = df.reset_index(drop=True)
            self.transform = transform
        def __len__(self):
            return len(self.df)
        def __getitem__(self, idx):
            row = self.df.iloc[idx]
            img = cv2.imread(row['img_path'])
            if img is None:
                raise FileNotFoundError(f"Cannot read: {row['img_path']}")
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if self.transform:
                img = self.transform(image=img)['image']
            return img, int(row['label'])

    train_ds = HAM10000Dataset(train_ham, ham_train_transforms)
    val_ds = HAM10000Dataset(val_ham, ham_val_transforms)

    BATCH = 64
    train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=True,
                          num_workers=2, pin_memory=True, drop_last=True)
    val_dl = DataLoader(val_ds, batch_size=BATCH, shuffle=False,
                        num_workers=2, pin_memory=True)
    print(f'DataLoaders: train={len(train_dl)} batches, val={len(val_dl)} batches')


# ────────────────────────────────────────────────────────────
# ## CELL 3 — Train EfficientNet-B3 on HAM10000 (10 epochs)


# ── Cell 9 ───────────────────────────────────────
if not SKIP:
    print('\n' + '=' * 60)
    print('  HAM10000 PRE-TRAINING (10 epochs)')
    print('=' * 60)

    # Create model: EfficientNet-B3 with ImageNet weights + new classifier
    backbone = timm.create_model('efficientnet_b3', pretrained=True, num_classes=HAM_NUM_CLASSES)
    backbone = backbone.to(device)

    # Class weights for HAM10000 (imbalanced dataset)
    from sklearn.utils.class_weight import compute_class_weight
    ham_weights = compute_class_weight('balanced', classes=np.arange(HAM_NUM_CLASSES),
                                       y=train_ham['label'].values)
    ham_weights_t = torch.tensor(ham_weights, dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=ham_weights_t, label_smoothing=0.05)

    optimizer = torch.optim.AdamW(backbone.parameters(), lr=3e-4, weight_decay=0.01)
    scaler = GradScaler()

    NUM_EPOCHS_HAM = 10
    best_f1 = 0.0
    start = time.time()

    for epoch in range(1, NUM_EPOCHS_HAM + 1):
        # Train
        backbone.train()
        running_loss = 0.0
        pbar = tqdm(train_dl, desc=f'HAM Epoch {epoch}/{NUM_EPOCHS_HAM}', leave=False)
        for imgs, labels in pbar:
            imgs = imgs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with autocast():
                logits = backbone(imgs)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(backbone.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            running_loss += loss.item() * imgs.size(0)
            pbar.set_postfix({'loss': f'{loss.item():.4f}'})

        # Validate
        backbone.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for imgs, labels in val_dl:
                imgs = imgs.to(device, non_blocking=True)
                with autocast():
                    logits = backbone(imgs)
                preds = logits.argmax(dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.numpy())
        val_f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
        train_loss = running_loss / len(train_dl.dataset)

        marker = ''
        if val_f1 > best_f1:
            best_f1 = val_f1
            marker = ' ★ BEST'
        print(f'Epoch {epoch:2d}/{NUM_EPOCHS_HAM} | Loss: {train_loss:.4f} | Val F1: {val_f1:.4f}{marker}')

    elapsed = time.time() - start
    print(f'\nHAM10000 pre-training done in {elapsed/60:.1f} minutes (best F1: {best_f1:.4f})')


# ────────────────────────────────────────────────────────────
# ## CELL 4 — Extract & Save Backbone Weights (excluding classifier)


# ── Cell 11 ───────────────────────────────────────
if not SKIP:
    # Extract backbone weights (everything except the final classifier)
    # timm model with num_classes=7 has a 'classifier' layer we want to exclude
    backbone_state = {}
    full_state = backbone.state_dict()
    for k, v in full_state.items():
        if k.startswith('classifier'):
            continue  # Skip the HAM10000-specific classifier head
        backbone_state[k] = v

    torch.save(backbone_state, HAM_BACKBONE_PATH)
    print(f'\n✅ Backbone weights saved to {HAM_BACKBONE_PATH}')
    print(f'   Keys saved: {len(backbone_state)} (excluded classifier head)')

    # Verify it can be loaded into a fresh backbone
    test_model = timm.create_model('efficientnet_b3', pretrained=False,
                                    num_classes=0, global_pool='')
    msg = test_model.load_state_dict(backbone_state, strict=False)
    print(f'   Verification: missing={len(msg.missing_keys)}, unexpected={len(msg.unexpected_keys)}')
    if len(msg.missing_keys) == 0:
        print('   ✅ All backbone keys loaded successfully')
    else:
        print(f'   ⚠️ Missing keys: {msg.missing_keys[:5]}...')

    del backbone, test_model
    gc.collect()
    torch.cuda.empty_cache()


# ────────────────────────────────────────────────────────────
# ## CELL 5 — Final Summary


# ── Cell 13 ───────────────────────────────────────
# ============================================================
# Final Summary
# ============================================================
print('\n' + '=' * 60)
print('  HAM10000 PRE-TRAINING COMPLETE')
print('=' * 60)
print(f'  Output: {HAM_BACKBONE_PATH}')
print(f'  → Run 04a_training_phase1_V6.0.py next')
print(f'    It will auto-detect and load these weights.')
print('=' * 60)
