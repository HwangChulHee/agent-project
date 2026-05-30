import sys, glob, os
import numpy as np

def describe(obj, indent=0, max_items=5, max_str=80):
    pad = "  " * indent
    if isinstance(obj, dict):
        print(f"{pad}dict (keys={len(obj)}): {list(obj.keys())[:max_items]}")
        for k in list(obj.keys())[:max_items]:
            print(f"{pad}  key '{k}':")
            describe(obj[k], indent + 2, max_items, max_str)
    elif isinstance(obj, np.ndarray):
        print(f"{pad}ndarray shape={obj.shape} dtype={obj.dtype}")
        flat = obj.ravel()
        print(f"{pad}  sample: {flat[:max_items].tolist() if flat.size else []}")
        if obj.dtype == object and obj.size:
            print(f"{pad}  first element detail:")
            describe(flat[0], indent + 2, max_items, max_str)
    elif isinstance(obj, (list, tuple)):
        print(f"{pad}{type(obj).__name__} (len={len(obj)})")
        if obj:
            print(f"{pad}  first element:")
            describe(obj[0], indent + 2, max_items, max_str)
    else:
        s = repr(obj)
        print(f"{pad}{type(obj).__name__}: {s[:max_str] + ('...' if len(s) > max_str else '')}")

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    npys = sorted(glob.glob(os.path.join(folder, "*.npy")))
    print(f"[도면 폴더] {folder}")
    print(f"[.npy 파일 수] {len(npys)}\n")
    for p in npys:
        print(f"===== {os.path.basename(p)} =====")
        obj = np.load(p, allow_pickle=True)
        if isinstance(obj, np.ndarray) and obj.dtype == object and obj.shape == ():
            obj = obj.item()
        describe(obj)
        print()

if __name__ == "__main__":
    main()
