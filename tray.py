"""Symbol im Infobereich der Windows-Taskleiste (unten rechts, ggf. unter dem ^-Pfeil).

Nur Python-Standardbibliothek (ctypes). Linksklick öffnet Jahresring im Browser,
Rechtsklick zeigt ein Menü mit Öffnen, Datenordner, Protokoll und Beenden.
"""
import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_NULL = 0x0002, 0x0010, 0x0111, 0x0000
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_NONOTIFY = 0x0002, 0x0100, 0x0080
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wintypes.HICON
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.LPVOID]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

_zustand = {}


def beenden():
    """Von außen aufrufbar (z. B. Ein/Aus-Knopf im Browser): Symbol entfernen und Programm beenden."""
    hwnd = _zustand.get("hwnd")
    if hwnd:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True
    return False


def starten(titel, symbol_pfad, eintraege, beim_beenden, linksklick=None, info=None):
    """Blockiert mit der Windows-Nachrichtenschleife.
    eintraege: Liste von (Text, Funktion) bzw. None für eine Trennlinie; der erste Eintrag ist fett.
    """
    hinst = kernel32.GetModuleHandleW(None)
    taskbar_neu = user32.RegisterWindowMessageW("TaskbarCreated")
    befehle = {}

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAY
    nid.szTip = titel[:127]
    h_icon = None
    if symbol_pfad and os.path.isfile(symbol_pfad):
        h_icon = user32.LoadImageW(None, symbol_pfad, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
    nid.hIcon = h_icon or user32.LoadIconW(None, ctypes.c_void_p(32512))  # IDI_APPLICATION

    def menue(hwnd):
        h = user32.CreatePopupMenu()
        befehle.clear()
        for n, e in enumerate(eintraege, 1):
            if e is None:
                user32.AppendMenuW(h, MF_SEPARATOR, 0, None)
            else:
                user32.AppendMenuW(h, MF_STRING, n, e[0])
                befehle[n] = e[1]
        user32.SetMenuDefaultItem(h, 1, 0)
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenu(h, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(h)
        if cmd and cmd in befehle:
            try:
                befehle[cmd]()
            except Exception as f:  # noqa: BLE001
                print("Menüfehler:", f)

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            ereignis = lparam & 0xFFFF
            if ereignis in (WM_LBUTTONUP, WM_LBUTTONDBLCLK) and linksklick:
                if ereignis == WM_LBUTTONUP:
                    linksklick()
            elif ereignis == WM_RBUTTONUP:
                menue(hwnd)
            return 0
        if msg == taskbar_neu and taskbar_neu:
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
            return 0
        if msg == WM_CLOSE:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)
    _zustand["proc"] = proc  # Referenz halten, sonst räumt Python den Rückruf weg

    wc = WNDCLASSW()
    wc.lpfnWndProc = proc
    wc.hInstance = hinst
    wc.lpszClassName = "JahresringTray"
    user32.RegisterClassW(ctypes.byref(wc))
    hwnd = user32.CreateWindowExW(0, wc.lpszClassName, titel, 0, 0, 0, 0, 0, None, None, hinst, None)
    if not hwnd:
        raise OSError("Fenster für das Taskleistensymbol konnte nicht erstellt werden")
    _zustand["hwnd"] = hwnd
    nid.hWnd = hwnd
    if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        raise OSError("Taskleistensymbol konnte nicht angelegt werden")
    if info:
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = info[0][:63]
        nid.szInfo = info[1][:255]
        nid.dwInfoFlags = 0x01  # NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    _zustand.pop("hwnd", None)
    beim_beenden()
