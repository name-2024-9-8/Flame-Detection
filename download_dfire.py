"""
D-Fire 数据集下载与准备脚本

用法:
    python download_dfire.py                  # 下载到默认位置 data/dfire/
    python download_dfire.py --target ./mydata  # 自定义目标目录
    python download_dfire.py --force           # 强制重新下载

数据集来源: Kaggle (tunuyn/d-fire)
  - ~21,000 张图片, 2 类 (fire=0, smoke=1)
  - 自动处理目录结构差异、生成 data.yaml、拆分验证集

依赖: pip install kagglehub
"""
import argparse
import random
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TARGET = PROJECT_ROOT / "data" / "dfire"

SEED = 42


def detect_structure(src_dir: Path) -> dict:
    """
    探测下载目录的实际结构，返回标准化描述:
    {split: {"images": Path, "labels": Path or None}}
    """
    result = {}
    for split_name in ("train", "valid", "val", "test"):
        if not (src_dir / split_name).is_dir():
            continue
        split_dir = src_dir / split_name
        # 常见结构1: split/images/ + split/labels/
        if (split_dir / "images").is_dir():
            result[split_name] = {
                "images": split_dir / "images",
                "labels": split_dir / "labels" if (split_dir / "labels").is_dir() else None,
            }
        else:
            # 常见结构2: 图片和标签混在同一目录
            result[split_name] = {"images": split_dir, "labels": split_dir}
    return result


def find_data_yaml(src_dir: Path) -> Path | None:
    """递归搜索 data.yaml"""
    for p in src_dir.rglob("data.yaml"):
        return p
    for p in src_dir.rglob("*.yaml"):
        if p.name != "data.yaml":
            return p
    return None


def generate_data_yaml(target_dir: Path, splits: list[str]) -> None:
    """从头生成 data.yaml"""
    lines = [
        f"path: {target_dir.as_posix()}",
        f"train: train/images",
        f"val: val/images",
        f"test: test/images" if "test" in splits else "",
        "",
        "nc: 2",
        "names:",
        "  0: fire",
        "  1: smoke",
    ]
    yaml_path = target_dir / "data.yaml"
    yaml_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  已生成 data.yaml")


def organize_split(src_split: dict, dst_dir: Path, split_name: str) -> int:
    """将原始 split 数据拷贝到标准的 images/ + labels/ 目录结构，返回文件数"""
    dst_images = dst_dir / split_name / "images"
    dst_labels = dst_dir / split_name / "labels"
    dst_images.mkdir(parents=True, exist_ok=True)
    dst_labels.mkdir(parents=True, exist_ok=True)

    src_images = src_split["images"]
    src_labels = src_split["labels"]

    count = 0
    for img_file in src_images.iterdir():
        if img_file.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
            continue
        count += 1

        # 复制图片
        dst_img = dst_images / img_file.name
        if not dst_img.exists():
            shutil.copy2(img_file, dst_img)

        # 查找对应标签
        label_name = img_file.stem + ".txt"
        if src_labels:
            src_label = src_labels / label_name
            dst_label = dst_labels / label_name
            if src_label.exists() and not dst_label.exists():
                shutil.copy2(src_label, dst_label)

    return count


def split_train_val(target_dir: Path, val_ratio: float = 0.15) -> None:
    """从 train 中拆分出 val (如果原始数据集没有 valid/val)"""
    train_images = target_dir / "train" / "images"
    train_labels = target_dir / "train" / "labels"

    if not train_images.exists():
        return

    val_images = target_dir / "val" / "images"
    val_labels = target_dir / "val" / "labels"
    val_images.mkdir(parents=True, exist_ok=True)
    val_labels.mkdir(parents=True, exist_ok=True)

    # 收集所有有标签的图片
    img_files = sorted([f for f in train_images.iterdir()
                        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")])

    # 按视频来源分组 (D-Fire 文件名格式: vid_frame.jpg, 取 vid 部分进行分组避免数据泄漏)
    # D-Fire 常见命名: 前缀_数字.jpg 或 纯数字.jpg
    # 简单处理: 打乱后按比例拆分
    random.seed(SEED)
    random.shuffle(img_files)

    val_count = max(1, int(len(img_files) * val_ratio))
    val_files = img_files[:val_count]

    print(f"  从 train 拆分 val: {len(img_files)} → train={len(img_files) - val_count}, val={val_count}")

    for img_file in val_files:
        label_file = train_labels / (img_file.stem + ".txt")
        # 移动图片到 val
        shutil.move(str(img_file), str(val_images / img_file.name))
        # 移动标签到 val
        if label_file.exists():
            shutil.move(str(label_file), str(val_labels / (img_file.stem + ".txt")))


def download_kagglehub(target_dir: Path) -> bool:
    """通过 kagglehub 下载 D-Fire 数据集"""
    try:
        import kagglehub
    except ImportError:
        print("[!] 需要安装 kagglehub: pip install kagglehub")
        return False

    print("正在从 Kaggle 下载 D-Fire 数据集 (tunuyn/d-fire)...")
    print("  这可能需要 5-15 分钟，取决于网络速度...\n")

    try:
        download_path = kagglehub.dataset_download("tunuyn/d-fire")
        download_path = Path(download_path)
        print(f"\n下载完成，缓存位置: {download_path}")
    except Exception as e:
        print(f"[!] 下载失败: {e}")
        print("[提示] 国内环境可能无法直连 Kaggle")
        print("  备用: 浏览器打开 https://www.kaggle.com/datasets/tunuyn/d-fire 手动下载")
        print("  解压后确保目录结构为: train/images/, train/labels/, test/images/, test/labels/")
        return False

    target_dir.mkdir(parents=True, exist_ok=True)

    # 穿透多层目录找到实际数据根目录
    src = download_path
    while True:
        items = [i for i in src.iterdir() if i.is_dir() and not i.name.startswith(".")]
        if len(items) == 1 and all(s not in ("train", "test", "valid", "val") for s in [i.name for i in items]):
            src = items[0]
        else:
            break

    print(f"数据根目录: {src}")
    print(f"内容: {[i.name for i in src.iterdir()]}\n")

    # 探测结构
    structure = detect_structure(src)
    if not structure:
        print(f"[!] 未识别出 train/valid/test 目录")
        print(f"  目录内容: {[i.name for i in src.iterdir()][:20]}")
        return False

    print("检测到的目录结构:")
    for split_name, paths in structure.items():
        img_count = len([f for f in paths["images"].iterdir()
                         if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")])
        label_count = 0
        if paths["labels"]:
            label_count = len(list(paths["labels"].glob("*.txt")))
        print(f"  {split_name}: {img_count} 张图片, {label_count} 个标签")

    # 查找或生成 data.yaml
    yaml_src = find_data_yaml(src)
    if yaml_src:
        print(f"\n找到原始 data.yaml: {yaml_src}")
    else:
        print("\n未找到 data.yaml，将自动生成")

    # 拷贝数据到目标目录
    print(f"\n拷贝到 {target_dir} ...")
    has_valid = "valid" in structure or "val" in structure

    for split_name, split_paths in structure.items():
        out_name = "val" if split_name in ("valid", "val") else split_name
        count = organize_split(split_paths, target_dir, out_name)
        print(f"  {out_name}: {count} 张图片")

    # 如果原始没有 valid/val，从 train 拆分
    if not has_valid and "train" in structure:
        print("\n原始数据集无验证集，从 train 拆分 15% 作为 val...")
        split_train_val(target_dir, val_ratio=0.15)

    # 生成或复制 data.yaml
    if yaml_src:
        dst_yaml = target_dir / "data.yaml"
        if yaml_src != dst_yaml:
            shutil.copy2(yaml_src, dst_yaml)
        # 修复路径
        content = dst_yaml.read_text(encoding="utf-8")
        content = f"path: {target_dir.as_posix()}\n" + "\n".join(
            [l for l in content.splitlines() if not l.startswith("path:")]
        )
        # 统一 val/valid 命名
        content = content.replace("valid:", "val:").replace("valid/", "val/")
        dst_yaml.write_text(content, encoding="utf-8")
        print(f"  已更新 data.yaml")
    else:
        splits = [s for s in ("train", "val", "test") if (target_dir / s).is_dir()]
        generate_data_yaml(target_dir, splits)

    return True


def validate(target_dir: Path) -> bool:
    """验证数据集完整性"""
    print("\n验证数据集...")

    yaml_path = target_dir / "data.yaml"
    if not yaml_path.exists():
        print("[!] 缺少 data.yaml")
        return False

    all_ok = True
    for split in ("train", "val", "test"):
        img_dir = target_dir / split / "images"
        lbl_dir = target_dir / split / "labels"
        if img_dir.is_dir():
            img_count = len([f for f in img_dir.iterdir()
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")])
            lbl_count = len(list(lbl_dir.glob("*.txt"))) if lbl_dir.is_dir() else 0
            print(f"  {split}: {img_count} 张图片, {lbl_count} 个标签")
            if img_count == 0:
                print(f"    [!] {split}/images 为空")
                all_ok = False
        else:
            print(f"  {split}: (未找到, 跳过)")

    if all_ok:
        print("\n[OK] 数据集验证通过")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="下载 D-Fire 数据集")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                        help=f"目标目录 (默认: {DEFAULT_TARGET})")
    parser.add_argument("--force", action="store_true",
                        help="强制重新下载 (覆盖已有数据)")
    args = parser.parse_args()

    target_dir = args.target.resolve()

    if target_dir.exists() and not args.force:
        has_data = (target_dir / "data.yaml").exists()
        if has_data:
            print(f"目标目录已有数据: {target_dir}")
            print("如需重新下载: python download_dfire.py --force")
            validate(target_dir)
            return

    if target_dir.exists() and args.force:
        print(f"删除已有数据: {target_dir}")
        shutil.rmtree(target_dir)

    success = download_kagglehub(target_dir)
    if not success:
        sys.exit(1)

    validate(target_dir)

    print(f"\n{'='*50}")
    print("D-Fire 数据集准备完成!")
    print(f"路径: {target_dir}")
    print(f"\n下一步: python train_dfire.py")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
