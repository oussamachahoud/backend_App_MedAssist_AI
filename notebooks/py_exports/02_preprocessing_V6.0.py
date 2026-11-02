# ═══ NOTEBOOK: 02_preprocessing_V6.0.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 02: Preprocessing V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | Unified Pre-Split Merge: PAD + ISIC + MCR-SL merged first, then patient-level stratified split (70/15/15) to produce highly robust Val/Test sets |
# | V5.0 | 7 ABCDE features, patient-level stratified split, class weight boost SCC×3 SEK×1.5 |
# | V4.2 | 11 features, basic split |
# 
# ## Purpose
# - Load & unify PAD-UFES-20, MCR-SL & ISIC 2019 datasets
# - Patient-level stratified train/val/test split (70/15/15) across unified dataset
# - meta_mask generation for partial clinical data
# - Smart imputation (median for numeric, mode for binary)
# - Scaling (StandardScaler for age, diameter_1)
# - Compute balanced class weights with boosts
# - Save preprocessing config JSON


# ── Cell 2 ───────────────────────────────────────
import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
import warnings
warnings.filterwarnings('ignore')

from google.colab import drive
drive.mount('/content/drive')

BASE_PATH = '/content/drive/MyDrive/MedAssist_AI'
DATASET_PATH = os.path.join(BASE_PATH, 'dataset')
ISIC_PATH = os.path.join(BASE_PATH, 'dataset_isic2019')
MCR_PATH = os.path.join(BASE_PATH, 'dataset_mcr_sl')
PROCESSED_PATH = os.path.join(BASE_PATH, 'data', 'processed')
os.makedirs(PROCESSED_PATH, exist_ok=True)

VERSION = 'V6.0'
CLASS_NAMES = ['ACK', 'BCC', 'MEL', 'NEV', 'SCC', 'SEK']
NUM_CLASSES = 6

SELECTED_FEATURES = ['age', 'gender', 'grew', 'bleed',
                     'diameter_1', 'skin_cancer_history', 'elevation']
NUMERIC_FEATURES = ['age', 'diameter_1']
BINARY_FEATURES = ['gender', 'grew', 'bleed',
                   'skin_cancer_history', 'elevation']
NUM_META = 7

RARE_CLASSES = ['SCC', 'ACK', 'MEL', 'SEK', 'NEV']

# ✅ UPDATED: ISIC targets increased for SCC, ACK, SEK
ISIC_TARGET_PER_CLASS = {
    'SCC': 628,   # ← 500 → 628 (all available)
    'ACK': 500,   # ← 450 → 500
    'MEL': 500,   # unchanged
    'SEK': 500,   # ← 400 → 500
    'NEV': 500,   # unchanged
}

# ✅ UPDATED: SCC cap raised to 900 to prevent undersampling
TRAIN_UNDERSAMPLE_CAP = {
    'ACK': 800,
    'MEL': 700,
    'SCC': 900,   # ← 700 → 900
    'SEK': 800,
    'NEV': 800,
}

MCR_CLASS_MAP = {
    'SCC': 'SCC',
    'AK':  'ACK',
    'MEL': 'MEL',
    'SK':  'SEK',
    'BCC': 'BCC',
    'NEV': 'NEV',
}

ISIC_CLASS_MAP = {
    'SCC': 'SCC',
    'AK':  'ACK',
    'MEL': 'MEL',
    'BKL': 'SEK',
    'NV':  'NEV',
}

print(f'✅ MedAssist AI {VERSION} — Preprocessing (Unified Pre-Split Merge)')
print(f'📋 Selected features ({NUM_META}): {SELECTED_FEATURES}')

# ── CELL 2: Load & Prepare PAD-UFES-20 ────────────────────────────────────
metadata_path = None
for name in ['metadata.csv', 'metadata (1).csv', 'metadata_pad.csv']:
    test_path = os.path.join(DATASET_PATH, name)
    if os.path.exists(test_path):
        metadata_path = test_path
        break

if not metadata_path:
    for root, dirs, files in os.walk(DATASET_PATH):
        for f in files:
            if f.lower().startswith('metadata') and f.lower().endswith('.csv') and 'isic' not in f.lower():
                metadata_path = os.path.join(root, f)
                break
        if metadata_path:
            break

if not metadata_path:
    raise FileNotFoundError('❌ No valid PAD-UFES-20 metadata file found')

print(f'✅ Found PAD-UFES-20 metadata at: {metadata_path}')

pad_df = pd.read_csv(metadata_path)
print(f'✅ Loaded PAD-UFES-20: {len(pad_df)} rows')

if 'img_id' not in pad_df.columns:
    for col in ['image_id', 'image', 'filename']:
        if col in pad_df.columns:
            pad_df['img_id'] = pad_df[col]
            break

if 'patient_id' not in pad_df.columns:
    if 'img_id' in pad_df.columns:
        pad_df['patient_id'] = pad_df['img_id'].apply(
            lambda x: '_'.join(str(x).split('_')[:2]))
    else:
        pad_df['patient_id'] = range(len(pad_df))

if 'gender' in pad_df.columns:
    gender_map = {'MALE': 1, 'FEMALE': 0, 'male': 1, 'female': 0, 'M': 1, 'F': 0}
    pad_df['gender'] = pad_df['gender'].map(gender_map)

bool_map = {'TRUE': 1.0, 'FALSE': 0.0, 'UNK': np.nan, True: 1.0, False: 0.0}
for feat in ['grew', 'bleed', 'elevation']:
    if feat in pad_df.columns:
        pad_df[feat] = pad_df[feat].map(bool_map)

if 'skin_cancer_history' in pad_df.columns:
    pad_df['skin_cancer_history'] = pad_df['skin_cancer_history'].map(
        {True: 1.0, False: 0.0})

pad_df['source'] = 'PAD-UFES-20'
pad_df['clinical_complete'] = True

diag_encoder = LabelEncoder()
diag_encoder.fit(CLASS_NAMES)
pad_df['label'] = diag_encoder.transform(pad_df['diagnostic'])

encoder_path = os.path.join(PROCESSED_PATH, 'diagnostic_encoder.pkl')
with open(encoder_path, 'wb') as f:
    pickle.dump(diag_encoder, f)
print(f'saved -> {encoder_path}')

# ── CELL 3: Load & Merge Supplementary Datasets ───────────────────────────
print('✅ Merging datasets before split to create robust Val/Test sets...')

mcr_unified = os.path.join(MCR_PATH, 'unified_diagnosis.xlsx')
mcr_lesion  = os.path.join(MCR_PATH, 'lesion.xlsx')
mcr_subject = os.path.join(MCR_PATH, 'subject.xlsx')
mcr_image   = os.path.join(MCR_PATH, 'image.xlsx')

mcr_df = None
if all(os.path.exists(p) for p in [mcr_unified, mcr_lesion, mcr_subject, mcr_image]):
    df_diag   = pd.read_excel(mcr_unified)
    df_lesion = pd.read_excel(mcr_lesion)
    df_sub    = pd.read_excel(mcr_subject)
    df_img    = pd.read_excel(mcr_image)

    mcr_raw = (df_diag
               .merge(df_lesion, on='lesion_id')
               .merge(df_sub,    on='subject_id')
               .merge(df_img,    on='lesion_id'))
    mcr_raw = mcr_raw[mcr_raw['unified_diagnosis'].isin(MCR_CLASS_MAP.keys())].copy()
    mcr_raw['diagnostic'] = mcr_raw['unified_diagnosis'].map(MCR_CLASS_MAP)

    mcr_raw['age']                 = mcr_raw['age']
    mcr_raw['gender']              = mcr_raw['sex'].map({'Male': 1, 'Female': 0})
    mcr_raw['diameter_1']          = mcr_raw['diameter']
    mcr_raw['skin_cancer_history'] = mcr_raw['h_skin_cancer'].map({'Yes': 1, 'No': 0})
    for feat in ['grew', 'bleed', 'elevation']:
        mcr_raw[feat] = np.nan

    mcr_df = mcr_raw[mcr_raw['diagnostic'].isin(RARE_CLASSES)].copy()
    mcr_df['source']            = 'MCR-SL'
    mcr_df['clinical_complete'] = True
    mcr_df['patient_id']        = 'MCR_' + mcr_df['subject_id'].astype(str)
    mcr_df['img_id']            = mcr_df['image_id'].astype(str)
    mcr_df['img_filename']      = mcr_df['image_id'].astype(str) + '.png'
    mcr_df['label']             = diag_encoder.transform(mcr_df['diagnostic'])
    print(f'📊 Loaded MCR-SL rare classes (incl. NEV): {len(mcr_df)} images')
    print(f'   MCR-SL NEV images: {(mcr_df["diagnostic"] == "NEV").sum()}')
else:
    print('⚠️ MCR-SL dataset not found, skipping')

isic_metadata = os.path.join(ISIC_PATH, 'ISIC_2019_Training_Metadata.csv')
isic_gt       = os.path.join(ISIC_PATH, 'ISIC_2019_Training_GroundTruth.csv')
isic_df = None
if os.path.exists(isic_metadata) and os.path.exists(isic_gt):
    isic_meta   = pd.read_csv(isic_metadata)
    isic_ground = pd.read_csv(isic_gt)
    isic_raw    = isic_meta.merge(isic_ground, on='image')

    isic_raw['diagnostic'] = None
    for isic_class, target_class in ISIC_CLASS_MAP.items():
        isic_raw.loc[isic_raw[isic_class] == 1.0, 'diagnostic'] = target_class
    isic_raw = isic_raw[isic_raw['diagnostic'].notna()].copy()

    isic_sampled = []
    for diag, target_count in ISIC_TARGET_PER_CLASS.items():
        diag_df = isic_raw[isic_raw['diagnostic'] == diag].copy()
        if len(diag_df) == 0:
            print(f'   ⚠️  ISIC {diag}: 0 images found')
            continue
        diag_df['clinical_score'] = (
            diag_df['age_approx'].notna().astype(int) +
            diag_df['sex'].notna().astype(int) +
            diag_df['anatom_site_general'].notna().astype(int))
        diag_df = diag_df.sort_values('clinical_score', ascending=False)
        sampled = diag_df.head(target_count).copy()
        isic_sampled.append(sampled)
        print(f'   ISIC {diag}: took {len(sampled)}/{len(diag_df)} available')

    if isic_sampled:
        isic_df = pd.concat(isic_sampled, ignore_index=True)
        isic_df['age']    = isic_df['age_approx']
        isic_df['gender'] = isic_df['sex'].map({'male': 1, 'female': 0})
        for feat in ['grew', 'bleed', 'diameter_1', 'skin_cancer_history', 'elevation']:
            isic_df[feat] = np.nan
        isic_df['source']            = 'ISIC-2019'
        isic_df['clinical_complete'] = False
        isic_df['img_id']            = isic_df['image'].astype(str)
        isic_df['img_filename']      = isic_df['image'].astype(str) + '.jpg'
        if 'lesion_id' in isic_df.columns:
            isic_df['patient_id'] = 'ISIC_' + isic_df['lesion_id'].fillna(
                isic_df['image']).astype(str)
        else:
            isic_df['patient_id'] = 'ISIC_' + isic_df['image'].astype(str)
        isic_df['label'] = diag_encoder.transform(isic_df['diagnostic'])
        print(f'📊 Loaded ISIC 2019 selective: {len(isic_df)} images')
else:
    print('⚠️ ISIC 2019 dataset not found, skipping')

df_master = pad_df.copy()
if mcr_df is not None:
    df_master = pd.concat([df_master, mcr_df], ignore_index=True)
if isic_df is not None:
    df_master = pd.concat([df_master, isic_df], ignore_index=True)

def get_img_filename(row):
    existing = row.get('img_filename', None)
    if existing and str(existing) not in ('', 'nan', 'None'):
        return str(existing)
    img_id = str(row.get('img_id', ''))
    if not img_id.endswith('.png'):
        img_id = img_id + '.png'
    return img_id

df_master['img_filename'] = df_master.apply(get_img_filename, axis=1)

initial_len = len(df_master)
df_master = df_master.drop_duplicates(
    subset=['img_filename'], keep='first').reset_index(drop=True)
print(f'📊 Unified master dataset: {len(df_master)} images '
      f'(removed {initial_len - len(df_master)} duplicates)')
print('📊 Master class distribution:')
print(df_master['diagnostic'].value_counts().reindex(CLASS_NAMES, fill_value=0).to_dict())

# ── CELL 4: Patient-Level Stratified Split ────────────────────────────────
print('✅ Performing Patient-Level Stratified split on unified dataset...')

patient_labels = (df_master.groupby('patient_id')['label']
                  .agg(lambda x: x.mode()[0])
                  .reset_index())
patient_labels.columns = ['patient_id', 'label']

patients = patient_labels['patient_id'].values
labels   = patient_labels['label'].values

print('🔍 Searching 10 folds for best test-set class balance...')
sgkf_search = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=42)

best_trainval_idx = None
best_test_idx     = None
best_balance      = float('inf')
best_fold_num     = -1

for fold_num, (tv_idx, te_idx) in enumerate(
        sgkf_search.split(patients, labels, groups=patients)):
    test_lab = labels[te_idx]
    counts   = np.bincount(test_lab, minlength=NUM_CLASSES)
    balance  = counts.max() / counts.min() if counts.min() > 0 else float('inf')
    dist_str = ' | '.join(f'{CLASS_NAMES[i]}:{counts[i]}' for i in range(NUM_CLASSES))
    print(f'  Fold {fold_num:02d}: balance={balance:.2f}  [{dist_str}]')
    if balance < best_balance:
        best_balance      = balance
        best_trainval_idx = tv_idx
        best_test_idx     = te_idx
        best_fold_num     = fold_num

print(f'\n✅ Selected fold {best_fold_num} (balance ratio = {best_balance:.2f})')

trainval_patients = set(patients[best_trainval_idx])
test_patients     = set(patients[best_test_idx])

trainval_df = patient_labels[patient_labels['patient_id'].isin(trainval_patients)]
tv_patients = trainval_df['patient_id'].values
tv_labels   = trainval_df['label'].values

sgkf2 = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=42)
for train_idx, val_idx in sgkf2.split(tv_patients, tv_labels, groups=tv_patients):
    break

train_patients = set(tv_patients[train_idx])
val_patients   = set(tv_patients[val_idx])

df_master['split'] = 'train'
df_master.loc[df_master['patient_id'].isin(val_patients),  'split'] = 'val'
df_master.loc[df_master['patient_id'].isin(test_patients), 'split'] = 'test'

assert len(train_patients & val_patients)  == 0, 'Leakage: train ∩ val'
assert len(train_patients & test_patients) == 0, 'Leakage: train ∩ test'
assert len(val_patients   & test_patients) == 0, 'Leakage: val ∩ test'

train_df = df_master[df_master['split'] == 'train'].copy().reset_index(drop=True)
val_df   = df_master[df_master['split'] == 'val'  ].copy().reset_index(drop=True)
test_df  = df_master[df_master['split'] == 'test' ].copy().reset_index(drop=True)

print('📊 Patient-level stratified split results (before undersampling):')
for split_name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
    pct   = len(split_df) / len(df_master) * 100
    n_pat = split_df['patient_id'].nunique()
    print(f'  {split_name:5s}: {len(split_df):4d} images ({pct:.1f}%), {n_pat} patients')
print('✅ Patient leakage verification check: Passed with zero overlap.')

# ── Undersampling ─────────────────────────────────────────────────────────
print('\n🔄 Applying per-class undersampling on train split...')
undersampled_parts = []
for cls_name in CLASS_NAMES:
    cls_idx = CLASS_NAMES.index(cls_name)
    cls_df  = train_df[train_df['label'] == cls_idx].copy()
    cap     = TRAIN_UNDERSAMPLE_CAP.get(cls_name, None)
    if cap is not None and len(cls_df) > cap:
        print(f'  {cls_name}: {len(cls_df)} → {cap} (undersampled)')
        cls_df = cls_df.sample(n=cap, random_state=42)
    else:
        print(f'  {cls_name}: {len(cls_df)} (kept as-is)')
    undersampled_parts.append(cls_df)
train_df = pd.concat(undersampled_parts, ignore_index=True)

# ── Oversampling ──────────────────────────────────────────────────────────
print('\n🔄 Applying per-class oversampling on train split...')
# ✅ UPDATED: SCC target raised to 800
OVERSAMPLE_TARGETS = {'SCC': 800, 'MEL': 700}

for cls_name, target in OVERSAMPLE_TARGETS.items():
    cls_idx = CLASS_NAMES.index(cls_name)
    cls_df  = train_df[train_df['label'] == cls_idx].copy()
    to_add  = max(0, target - len(cls_df))
    if to_add > 0:
        extra = cls_df.sample(n=to_add, replace=True, random_state=42)
        train_df = pd.concat([train_df, extra], ignore_index=True)
        print(f'  {cls_name}: {len(cls_df)} → {len(cls_df) + to_add} (+{to_add} oversampled)')
    else:
        print(f'  {cls_name}: {len(cls_df)} (no oversampling needed)')

print(f'\n📊 After under/oversampling — train: {len(train_df)} images')
dist_after = train_df['diagnostic'].value_counts().reindex(CLASS_NAMES, fill_value=0)
print(f'  Distribution: {dict(dist_after)}')

# ── CELL 5: Leakage Check ─────────────────────────────────────────────────
print('🔍 Checking for duplicate file cross-split leakage...')
train_files    = set(train_df['img_filename'].tolist())
val_files      = set(val_df['img_filename'].tolist())
test_files     = set(test_df['img_filename'].tolist())
overlap_val    = train_files & val_files
overlap_test   = train_files & test_files

if overlap_val or overlap_test or (val_files & test_files):
    print(f'   🚨 LEAKAGE DETECTED! val:{len(overlap_val)}, test:{len(overlap_test)}')
    train_df = train_df[
        ~train_df['img_filename'].isin(overlap_val | overlap_test)
    ].reset_index(drop=True)
else:
    print('   ✅ Zero file-level overlap found between splits.')

# ── CELL 6: Imputation & Scaling ──────────────────────────────────────────
print('✅ Applying smart features processing & scaling on splits...')

for feat in SELECTED_FEATURES:
    for split_df in [train_df, val_df, test_df]:
        split_df[feat] = pd.to_numeric(split_df[feat], errors='coerce')

def create_meta_mask(row):
    return [1 if not pd.isna(row[f]) else 0 for f in SELECTED_FEATURES]

for split_df in [train_df, val_df, test_df]:
    split_df['meta_mask'] = split_df.apply(create_meta_mask, axis=1)

complete_mask    = train_df['clinical_complete'] == True
impute_values_num = {}
for feat in NUMERIC_FEATURES:
    median_val = train_df.loc[complete_mask, feat].median()
    if pd.isna(median_val):
        median_val = 0.0
    impute_values_num[feat] = median_val
    for split_df in [train_df, val_df, test_df]:
        split_df[feat] = split_df[feat].fillna(median_val)

impute_values_bin = {}
for feat in BINARY_FEATURES:
    mode_series = train_df.loc[complete_mask, feat].mode()
    mode_val    = mode_series[0] if len(mode_series) > 0 else 0
    impute_values_bin[feat] = mode_val
    for split_df in [train_df, val_df, test_df]:
        split_df[feat] = split_df[feat].fillna(mode_val)

scaler = StandardScaler()
if NUMERIC_FEATURES:
    scaler.fit(train_df[NUMERIC_FEATURES])
    train_df[NUMERIC_FEATURES] = scaler.transform(train_df[NUMERIC_FEATURES])
    val_df[NUMERIC_FEATURES]   = scaler.transform(val_df[NUMERIC_FEATURES])
    test_df[NUMERIC_FEATURES]  = scaler.transform(test_df[NUMERIC_FEATURES])

print('✅ Smart clinical features processed, scaled and masked.')

imputer_path = os.path.join(PROCESSED_PATH, 'imputer.pkl')
scaler_path  = os.path.join(PROCESSED_PATH, 'scaler.pkl')
with open(imputer_path, 'wb') as f:
    pickle.dump({'numeric_medians': impute_values_num,
                 'binary_modes':    impute_values_bin}, f)
with open(scaler_path, 'wb') as f:
    pickle.dump(scaler, f)
print(f'saved -> {imputer_path}')
print(f'saved -> {scaler_path}')

# ── CELL 7: Class Weights ─────────────────────────────────────────────────
from sklearn.utils.class_weight import compute_class_weight

def compute_smart_class_weights(train_df, class_names):
    y_train        = train_df['label'].values
    unique_classes = np.arange(len(class_names))
    weights = compute_class_weight('balanced', classes=unique_classes, y=y_train)

    # ✅ UPDATED: SCC 3.5 (was 2.5), BCC 0.5 (was 0.7)
    boosts = {
      'SCC': 2.8,   # يرفع SCC لنفس مستوى ACK/SEK
    'MEL': 2.0,   # ثابت — أداؤه مستقر
    'ACK': 2.8,   # يحافظ على قوة Run 1
    'SEK': 2.8,   # يحافظ على قوة Run 1
    'NEV': 0.7,   # أقل من Run 1 (0.8) — NEV recall 94% مرتفع
    'BCC': 0.6,   # أقل من Run 2 (0.8) — BCC سهل لا يحتاج وزن
      }

    for cls, boost in boosts.items():
        idx = class_names.index(cls)
        weights[idx] *= boost

    weights = weights / weights.sum() * len(class_names)

    print('📊 Smart Class Weights (balanced + boosts):')
    for i, name in enumerate(class_names):
        print(f'  {name}: {weights[i]:.4f}')
    return weights

class_weights_np = compute_smart_class_weights(train_df, CLASS_NAMES)
weights_path = os.path.join(PROCESSED_PATH, 'class_weights.npy')
np.save(weights_path, class_weights_np)
print(f'saved -> {weights_path}')

# ── CELL 8: Save CSVs & Config ────────────────────────────────────────────
save_cols = (['img_filename', 'label', 'diagnostic', 'patient_id',
               'source', 'clinical_complete', 'meta_mask'] + SELECTED_FEATURES)
save_cols = [c for c in save_cols if c in train_df.columns]

for name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
    path = os.path.join(PROCESSED_PATH, f'{name}.csv')
    split_df[save_cols].to_csv(path, index=False)
    print(f'saved -> {path} ({len(split_df)} rows)')

print('\n📊 Final Split Class Distributions:')
for name, split_df in [('train', train_df), ('val', val_df), ('test', test_df)]:
    dist = split_df['diagnostic'].value_counts().reindex(CLASS_NAMES, fill_value=0)
    print(f'  {name:5s}: {dict(dist)}')

config = {
    'version':            'V6.0',
    'num_classes':        NUM_CLASSES,
    'class_names':        CLASS_NAMES,
    'num_meta_features':  NUM_META,
    'selected_features':  SELECTED_FEATURES,
    'numeric_features':   NUMERIC_FEATURES,
    'binary_features':    BINARY_FEATURES,
    'removed_features_vs_v42': ['itch', 'hurt', 'changed'],
    'img_size':           256,
    'normalization': {
        'mean': [0.485, 0.456, 0.406],
        'std':  [0.229, 0.224, 0.225],
    },
    'preprocessing': {
        'color_constancy': 'shades_of_gray_power6',
        'hair_removal':    'dullrazor_17x17_thresh10',
        'clahe':           'clip_limit_2.0',
    },
    'split_sizes': {
        'train': len(train_df),
        'val':   len(val_df),
        'test':  len(test_df),
    },
    'class_weights':    class_weights_np.tolist(),
    'scc_boost':        2.8,
    'mel_boost':        2.0,
    'ack_boost':       2.8,
    'sek_boost':       2.8,
    'nev_boost':        0.7,
    'bcc_boost':        0.6,
    'isic_nv_nev':      True,
    'undersample_caps': TRAIN_UNDERSAMPLE_CAP,
}

config_path = os.path.join(PROCESSED_PATH, 'preprocessing_config.json')
with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
print(f'saved -> {config_path}')
print(f'\n✅ Preprocessing V6.0 complete — ready for Notebook 03')
