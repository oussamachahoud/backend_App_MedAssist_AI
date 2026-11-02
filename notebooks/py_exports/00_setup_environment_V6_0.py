# ═══ NOTEBOOK: 00_setup_environment_V6_0.ipynb ═══


# ────────────────────────────────────────────────────────────
# # 🏥 MedAssist AI — Notebook 00: Setup Environment V6.0
# 
# ## Version History
# | Version | Changes |
# |---------|--------|
# | V6.0 | Full automatic pipeline: PAD-UFES-20 + ISIC 2019 + MCR-SL — download, zip to Drive (once), copy to SSD (every session) |
# | V5.0 | PAD-UFES-20 only, manual ISIC handling |
# | V4.2 | Manual dataset setup |
# 
# ## Purpose
# - Mount Google Drive & create all directory structure
# - Install required packages
# - **Download all 3 datasets automatically via Kaggle API (run once)**
# - Pack each dataset into a zip in Drive for fast SSD transfer
# - **Copy all zips to local SSD `/content/local_dataset/` (run every session)**
# - Final verification checklist
# 
# > ⚡ **Session Start Protocol:** Run CELL 0 → CELL 1 → CELL 2 → CELL 9 → CELL 10 at every new session
# > (Only CELL 3–8 need to run once ever)


# ────────────────────────────────────────────────────────────
# ## CELL 0 — Mount Drive & Create Directory Structure


# ── Cell 3 ───────────────────────────────────────
from google.colab import drive
drive.mount('/content/drive')
print('✅ Google Drive mounted successfully')

import os

# ===== Base Paths =====
BASE_PATH        = '/content/drive/MyDrive/MedAssist_AI'
PAD_PATH         = os.path.join(BASE_PATH, 'dataset')             # PAD-UFES-20
ISIC_PATH        = os.path.join(BASE_PATH, 'dataset_isic2019')    # ISIC 2019
MCR_PATH         = os.path.join(BASE_PATH, 'dataset_mcr_sl')      # MCR-SL

# ===== Directory Structure =====
dirs = [
    PAD_PATH,
    os.path.join(PAD_PATH, 'images'),
    ISIC_PATH,
    MCR_PATH,
    os.path.join(BASE_PATH, 'data'),
    os.path.join(BASE_PATH, 'data', 'processed'),
    os.path.join(BASE_PATH, 'models'),
    os.path.join(BASE_PATH, 'results'),
    os.path.join(BASE_PATH, 'results', 'mlruns'),
]
for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f'  {"✅" if os.path.isdir(d) else "❌"} {d}')

print(f'\n📁 BASE_PATH = {BASE_PATH}')

# ── CELL 1 boundary ──────────────────────────────────────────


# ────────────────────────────────────────────────────────────
# ## CELL 1 — Install Required Packages (%%capture suppresses output)


# ── Cell 5 ───────────────────────────────────────
%%capture install_output
!pip install torch torchvision --upgrade
!pip install timm==1.0.3
!pip install albumentations>=1.3.1
!pip install opencv-python-headless
!pip install mlflow>=2.10
!pip install pandas numpy scikit-learn matplotlib seaborn
!pip install openpyxl kaggle

print('✅ All packages installed')


# ────────────────────────────────────────────────────────────
# ## CELL 2 — Verify Package Versions & GPU


# ── Cell 7 ───────────────────────────────────────
import torch, torchvision, timm, albumentations, cv2, mlflow, sklearn
import pandas as pd, numpy as np

print('=' * 60)
print('🏥 MedAssist AI V6.0 — Environment Check')
print('=' * 60)
print(f'✅ PyTorch:        {torch.__version__}')
print(f'✅ TorchVision:    {torchvision.__version__}')
print(f'✅ Timm:           {timm.__version__}')
print(f'✅ Albumentations: {albumentations.__version__}')
print(f'✅ OpenCV:         {cv2.__version__}')
print(f'✅ MLflow:         {mlflow.__version__}')
print(f'✅ Scikit-learn:   {sklearn.__version__}')
print(f'✅ Pandas:         {pd.__version__}')
print(f'✅ NumPy:          {np.__version__}')
print('=' * 60)
print(f'✅ CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'✅ GPU: {torch.cuda.get_device_name(0)}')
    print(f'✅ VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
else:
    print('⚠️  GPU not found — switch runtime to GPU!')
print('=' * 60)

# Upload kaggle.json API key


# ────────────────────────────────────────────────────────────
# ## CELL 3 — Configure Kaggle API Key


# ── Cell 9 ───────────────────────────────────────
from google.colab import files
uploaded = files.upload()   # Upload kaggle.json when prompted


# ────────────────────────────────────────────────────────────
# ## CELL 4 — Kaggle Key Setup


# ── Cell 11 ───────────────────────────────────────
!mkdir -p ~/.kaggle
!mv kaggle.json ~/.kaggle/
!chmod 600 ~/.kaggle/kaggle.json
print('✅ Kaggle API key configured')

# ============================================================


# ────────────────────────────────────────────────────────────
# ## CELL 5 — Download PAD-UFES-20 (~500 MB | Run Once)


# ── Cell 13 ───────────────────────────────────────
# DATASET 1: PAD-UFES-20  (~500 MB)
# ============================================================
import os

metadata_path = os.path.join(PAD_PATH, 'metadata.csv')

if os.path.exists(metadata_path):
    print('✅ PAD-UFES-20 already in Drive — skipping download')
else:
    print('📥 Downloading PAD-UFES-20 (~500 MB)...')
    os.system(f'kaggle datasets download -d mahdavi1202/skin-cancer -p /content')
    print('📦 Extracting PAD-UFES-20...')
    os.system(f'unzip -q -o /content/skin-cancer.zip -d {PAD_PATH}')
    os.system(f'rm -f /content/skin-cancer.zip')
    print('✅ PAD-UFES-20 downloaded and extracted to Drive')

# Quick verify
import pandas as pd
df_pad = pd.read_csv(metadata_path)
print(f'   Rows: {len(df_pad)} | Classes: {df_pad["diagnostic"].nunique()}')
print(f'   {df_pad["diagnostic"].value_counts().to_dict()}')

# ============================================================
# DATASET 2: ISIC 2019  (~10.5 GB)


# ────────────────────────────────────────────────────────────
# ## CELL 6 — Download ISIC 2019 (~10.5 GB | Run Once)


# ── Cell 15 ───────────────────────────────────────
# ============================================================
import os

ISIC_GT   = os.path.join(ISIC_PATH, 'ISIC_2019_Training_GroundTruth.csv')
ISIC_META = os.path.join(ISIC_PATH, 'ISIC_2019_Training_Metadata.csv')
ISIC_IMGS = os.path.join(ISIC_PATH, 'ISIC_2019_Training_Input')

if os.path.exists(ISIC_GT) and os.path.isdir(ISIC_IMGS):
    n_imgs = len(os.listdir(ISIC_IMGS))
    print(f'✅ ISIC 2019 already in Drive ({n_imgs:,} images) — skipping download')
else:
    print('📥 Downloading ISIC 2019 (~10.5 GB) — this will take 10-20 min...')
    os.system(f'kaggle datasets download -d andrewmvd/isic-2019 -p /content')
    print('📦 Extracting ISIC 2019 to Drive...')
    os.system(f'unzip -q -o /content/isic-2019.zip -d {ISIC_PATH}')
    os.system(f'rm -f /content/isic-2019.zip')
    print('✅ ISIC 2019 downloaded and extracted to Drive')

# Quick verify
df_isic_gt = pd.read_csv(ISIC_GT)
print(f'   Rows: {len(df_isic_gt)} | Columns: {list(df_isic_gt.columns[:5])}...')

# ============================================================
# DATASET 3: MCR-SL  (~200 MB)
# ============================================================


# ────────────────────────────────────────────────────────────
# ## CELL 7 — Download MCR-SL (~200 MB | Run Once)


# ── Cell 17 ───────────────────────────────────────
import os

MCR_META = os.path.join(MCR_PATH, 'unified_diagnosis.xlsx')

# If MCR-SL was extracted into a subfolder, flatten it
if not os.path.exists(MCR_META) and os.path.exists(MCR_PATH):
    subdirs = [os.path.join(MCR_PATH, d) for d in os.listdir(MCR_PATH) if os.path.isdir(os.path.join(MCR_PATH, d))]
    if len(subdirs) == 1:
        inner_dir = subdirs[0]
        if os.path.exists(os.path.join(inner_dir, 'unified_diagnosis.xlsx')):
            print(f'📦 Flattening MCR-SL directory structure from {inner_dir}...')
            os.system(f'mv "{inner_dir}"/* "{MCR_PATH}/"')
            os.system(f'rmdir "{inner_dir}"')

if os.path.exists(MCR_META):
    print('✅ MCR-SL already in Drive — skipping download')
else:
    print('📥 Downloading MCR-SL (~200 MB) from Zenodo...')
    zenodo_url = "https://zenodo.org/records/17306338/files/MCR-SL_dataset.zip?download=1"
    os.system(f'wget -q -O /content/mcr-sl.zip "{zenodo_url}"')

    if os.path.exists('/content/mcr-sl.zip'):
        print('📦 Extracting MCR-SL...')
        os.system(f'unzip -q -o /content/mcr-sl.zip -d {MCR_PATH}')
        os.system('rm -f /content/mcr-sl.zip')
        
        # If it extracted into a subfolder, move it up
        subdirs = [os.path.join(MCR_PATH, d) for d in os.listdir(MCR_PATH) if os.path.isdir(os.path.join(MCR_PATH, d))]
        if len(subdirs) == 1 and not os.path.exists(os.path.join(MCR_PATH, 'unified_diagnosis.xlsx')):
            inner_dir = subdirs[0]
            if os.path.exists(os.path.join(inner_dir, 'unified_diagnosis.xlsx')):
                print(f'   Moving files up from {inner_dir}...')
                os.system(f'mv "{inner_dir}"/* "{MCR_PATH}/"')
                os.system(f'rmdir "{inner_dir}"')
                
        print('✅ MCR-SL downloaded and extracted to Drive')
    else:
        print('⚠️  MCR-SL Zenodo download failed.')
        print('    Manual option: Download the dataset from:')
        print('    🔗 https://zenodo.org/records/17306338')
        print(f'    Then extract and place the images folder and metadata.csv in: {MCR_PATH}')

# ============================================================


# ────────────────────────────────────────────────────────────
# ## CELL 8 — Pack All Datasets into Drive Zips (Run Once)


# ── Cell 19 ───────────────────────────────────────
# SSD OPTIMIZATION — Pack all datasets into zip files in Drive
# This is done ONCE and then reused every session.
# ============================================================
import os, zipfile, time

def create_zip_if_needed(zip_path, source_dirs_or_files, label, extensions=('.jpg', '.jpeg', '.png')):
    """
    Creates a flat zip archive from a list of source directories.
    If zip already exists, skips.
    """
    if os.path.exists(zip_path):
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        if size_mb > 1.0:
            print(f'✅ {label} zip already exists ({size_mb:.0f} MB) — skipping')
            return
        else:
            print(f'⚠️  {label} zip exists but is too small ({size_mb:.3f} MB) — recreating...')
            os.remove(zip_path)

    print(f'📦 Creating {label} zip ({zip_path})...')
    count = 0
    start = time.time()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
        for src in source_dirs_or_files:
            if not os.path.isdir(src):
                print(f'  ⚠️  Skipping missing dir: {src}')
                continue
            for fname in sorted(os.listdir(src)):
                if fname.lower().endswith(extensions):
                    zf.write(os.path.join(src, fname), fname)  # flat structure
                    count += 1
                    if count % 1000 == 0:
                        print(f'  ... {count:,} images added')

    elapsed = time.time() - start
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f'✅ {label} zip done: {count:,} images, {size_mb:.0f} MB in {elapsed:.0f}s')


# 1. PAD-UFES-20 zip
PAD_ZIP = os.path.join(PAD_PATH, 'images.zip')
pad_img_dirs = [
    os.path.join(PAD_PATH, 'imgs_part_1', 'imgs_part_1'),
    os.path.join(PAD_PATH, 'imgs_part_2', 'imgs_part_2'),
    os.path.join(PAD_PATH, 'imgs_part_3', 'imgs_part_3'),
]
create_zip_if_needed(PAD_ZIP, pad_img_dirs, 'PAD-UFES-20')

# 2. ISIC 2019 zip (this is large ~10 GB uncompressed, stored without compression)
ISIC_ZIP = os.path.join(ISIC_PATH, 'isic_2019_images.zip')
isic_img_dirs = [os.path.join(ISIC_PATH, 'ISIC_2019_Training_Input')]
create_zip_if_needed(ISIC_ZIP, isic_img_dirs, 'ISIC 2019')

# 3. MCR-SL zip
MCR_ZIP = os.path.join(MCR_PATH, 'mcr_sl_images.zip')
# MCR-SL images folder — adjust if folder name differs after extraction
# MCR-SL contains both 'clinical' and 'dermoscopic' images, we must include both!
mcr_candidates = ['dermoscopic', 'clinical', 'images', 'imgs', 'Images', 'image']
mcr_img_dirs = []
for c in mcr_candidates:
    p = os.path.join(MCR_PATH, c)
    if os.path.isdir(p):
        mcr_img_dirs.append(p)

if mcr_img_dirs:
    # If the zip already exists but only contains some images (e.g. from the old buggy version that missed clinical images), delete it to recreate it.
    if os.path.exists(MCR_ZIP):
        try:
            with zipfile.ZipFile(MCR_ZIP, 'r') as zf:
                num_files = len([m for m in zf.namelist() if not m.endswith('/')])
            if num_files < 1500: # Total is 2,131. If < 1500, it's missing clinical or dermoscopic!
                print(f'⚠️  MCR-SL zip exists but only has {num_files} files (missing clinical/dermoscopic). Deleting to recreate...')
                os.remove(MCR_ZIP)
        except Exception:
            pass
    create_zip_if_needed(MCR_ZIP, mcr_img_dirs, 'MCR-SL')
else:
    print('⚠️  MCR-SL image folder not found — skipping zip creation')

print('\n📋 Zip summary:')
for label, zpath in [('PAD-UFES-20', PAD_ZIP), ('ISIC 2019', ISIC_ZIP), ('MCR-SL', MCR_ZIP)]:
    if os.path.exists(zpath):
        size_mb = os.path.getsize(zpath) / (1024 * 1024)
        print(f'  ✅ {label}: {zpath} ({size_mb:.0f} MB)')
    else:
        print(f'  ⚠️  {label}: zip not found')

# ============================================================


# ────────────────────────────────────────────────────────────
# ## CELL 9 — ⚡ Copy All Datasets to /content/local_dataset/ (Run Every Session)


# ── Cell 21 ───────────────────────────────────────
# COPY ALL DATASETS TO LOCAL SSD  ← Run at EVERY session start
# Mirrors exactly CELL 1 in 04a / 04b / 05_evaluation.
# Each dataset zip is copied from Drive to /content/local_dataset/
# and extracted there.  Pre-Cache Cell (5.5) in each notebook then
# applies Shades-of-Gray + DullRazor and writes to /content/fast_images/.
# ============================================================
import os, time

LOCAL_DATASET = '/content/local_dataset'
os.makedirs(LOCAL_DATASET, exist_ok=True)

# ── helper ────────────────────────────────────────────────────
def copy_zip_to_ssd(zip_drive_path, local_zip_tmp, extract_dir, label, sample_subdir=None, min_images=100):
    """
    Copy zip from Drive to local SSD temp path, extract to extract_dir.
    Skips if sample_subdir already has enough files.
    """
    check_dir = os.path.join(extract_dir, sample_subdir) if sample_subdir else extract_dir
    if os.path.isdir(check_dir):
        n = len([f for f in os.listdir(check_dir) if os.path.isfile(os.path.join(check_dir, f))])
        if n > min_images:
            print(f'  ✅ {label}: already extracted ({n:,} files in {check_dir}) — skipping')
            return
    if not os.path.exists(zip_drive_path):
        print(f'  ⚠️  {label}: zip not found at {zip_drive_path} — skipping')
        return
    zip_mb = os.path.getsize(zip_drive_path) / (1024 ** 2)
    print(f'  📦 {label}: copying {zip_mb:.0f} MB zip from Drive to Colab SSD...')
    start = time.time()
    os.system(f'cp "{zip_drive_path}" "{local_zip_tmp}"')
    print(f'  📂 {label}: extracting to {extract_dir}...')
    os.makedirs(extract_dir, exist_ok=True)
    os.system(f'unzip -q "{local_zip_tmp}" -d "{extract_dir}"')
    os.system(f'rm -f "{local_zip_tmp}"')
    elapsed = time.time() - start
    check_dir2 = os.path.join(extract_dir, sample_subdir) if sample_subdir else extract_dir
    n = sum(len(fs) for _, _, fs in os.walk(check_dir2))
    print(f'  ✅ {label}: done in {elapsed:.0f}s — {n:,} files at {check_dir2}')

print('=' * 60)
print('  ⚡ Copying datasets to local SSD — run every session!')
print('=' * 60)

# 1. PAD-UFES-20 → /content/local_dataset/images/  (same path as 04a CELL 1)
copy_zip_to_ssd(
    zip_drive_path = PAD_ZIP,
    local_zip_tmp  = '/content/pad_images.zip',
    extract_dir    = os.path.join(LOCAL_DATASET, 'images'),
    label          = 'PAD-UFES-20',
    min_images     = 2000,
)

# 2. ISIC 2019 → /content/local_dataset/isic2019/
copy_zip_to_ssd(
    zip_drive_path = ISIC_ZIP,
    local_zip_tmp  = '/content/isic_images.zip',
    extract_dir    = os.path.join(LOCAL_DATASET, 'isic2019'),
    label          = 'ISIC 2019',
    min_images     = 2000,
)

# 3. MCR-SL → /content/local_dataset/mcr_sl/
copy_zip_to_ssd(
    zip_drive_path = MCR_ZIP,
    local_zip_tmp  = '/content/mcr_images.zip',
    extract_dir    = os.path.join(LOCAL_DATASET, 'mcr_sl'),
    label          = 'MCR-SL',
    min_images     = 2000,
)

print(f'\n✅ All datasets on local SSD under {LOCAL_DATASET}/')
print('   → /content/local_dataset/images/       ← PAD-UFES-20 (used by 04a CELL 1)')
print('   → /content/local_dataset/isic2019/     ← ISIC 2019')
print('   → /content/local_dataset/mcr_sl/       ← MCR-SL')
print('   Next step: run Pre-Cache Cell (5.5) inside 04a/04b/05')
print('   to apply preprocessing → /content/fast_images/')

LOCAL_IMAGES = os.path.join(LOCAL_DATASET, 'images')


# ────────────────────────────────────────────────────────────
# ## CELL 10 — Final Verification Checklist


# ── Cell 23 ───────────────────────────────────────
# ============================================================
# FINAL VERIFICATION CHECKLIST
# ============================================================
import os, pandas as pd

print('=' * 60)
print('🏥 MedAssist AI V6.0 — Setup Complete')
print('=' * 60)

checks = {
    'Google Drive mounted'                  : os.path.isdir(BASE_PATH),
    'PAD-UFES-20 metadata.csv'             : os.path.exists(os.path.join(PAD_PATH, 'metadata.csv')),
    'PAD-UFES-20 images.zip (Drive)'       : os.path.exists(PAD_ZIP),
    'ISIC 2019 GroundTruth.csv'            : os.path.exists(os.path.join(ISIC_PATH, 'ISIC_2019_Training_GroundTruth.csv')),
    'ISIC 2019 Metadata.csv'               : os.path.exists(os.path.join(ISIC_PATH, 'ISIC_2019_Training_Metadata.csv')),
    'ISIC 2019 images.zip (Drive)'         : os.path.exists(ISIC_ZIP),
    'MCR-SL unified_diagnosis.xlsx'        : os.path.exists(os.path.join(MCR_PATH, 'unified_diagnosis.xlsx')),
    'MCR-SL images.zip (Drive)'            : os.path.exists(MCR_ZIP),
    'data/processed/ exists'               : os.path.isdir(os.path.join(BASE_PATH, 'data', 'processed')),
    'models/ exists'                        : os.path.isdir(os.path.join(BASE_PATH, 'models')),
    'results/ exists'                       : os.path.isdir(os.path.join(BASE_PATH, 'results')),
    'PAD-UFES-20 SSD copy ready'           : os.path.isdir(LOCAL_IMAGES) and len(os.listdir(LOCAL_IMAGES)) > 100,
    'ISIC 2019 SSD copy ready'             : os.path.isdir(os.path.join(LOCAL_DATASET, 'isic2019')),
    'MCR-SL SSD copy ready'                : os.path.isdir(os.path.join(LOCAL_DATASET, 'mcr_sl')),
}

all_ok = True
for name, ok in checks.items():
    icon = '✅' if ok else '❌'
    print(f'  {icon} {name}')
    if not ok:
        all_ok = False

print('=' * 60)
if all_ok:
    print('🎉 All checks passed! Ready for Notebook 01 → 02 → ...')
else:
    print('⚠️  Some checks failed — review the items marked ❌ above.')
print('=' * 60)
