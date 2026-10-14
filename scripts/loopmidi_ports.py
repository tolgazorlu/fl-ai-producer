"""Create the two loopMIDI ports flstudio-mcp needs by driving the loopMIDI window.

loopMIDI has no CLI; its ports live only while the app runs (it re-creates saved
ports on start). We use plain ctypes (no pywin32: Smart App Control blocks its DLLs).
"""
import ctypes
import ctypes.wintypes as w
import sys
import time

PORTS = ("FLStudioMCP RX", "FLStudioMCP TX")
WM_SETTEXT, BM_CLICK = 0x000C, 0x00F5
u = ctypes.windll.user32
EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)


def existing_ports() -> set[str]:
    import mido

    names = set(mido.get_input_names()) | set(mido.get_output_names())
    return {n for n in names}


def find_child(hwnd, cls_want, txt_want=None):
    out = []

    def cb(h, _):
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, cls, 256)
        txt = ctypes.create_unicode_buffer(512)
        u.GetWindowTextW(h, txt, 512)
        if cls.value == cls_want and (txt_want is None or txt.value == txt_want):
            out.append(h)
        return True

    u.EnumChildWindows(hwnd, EnumChildProc(cb), 0)
    return out[0] if out else None


def main() -> int:
    hwnd = u.FindWindowW(None, "loopMIDI")
    if not hwnd:
        print("loopMIDI window not found. Start loopMIDI first.")
        return 1
    have = existing_ports()
    edit = find_child(hwnd, "TEdit")
    plus = find_child(hwnd, "TButton", "+")
    for name in PORTS:
        if any(n.startswith(name) for n in have):
            print(f"ok      {name}")
            continue
        u.SendMessageW(edit, WM_SETTEXT, 0, name)
        time.sleep(0.3)
        u.SendMessageW(plus, BM_CLICK, 0, 0)
        time.sleep(1.0)
        print(f"created {name}")
    print("ports now:", sorted(existing_ports()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
