#define UNICODE
#define _UNICODE
#include <windows.h>
#include <gdiplus.h>
#include <shellapi.h>
#include <string>
#include <vector>
#include <cstdlib>

#pragma comment(lib, "gdiplus.lib")
using namespace Gdiplus;

static const wchar_t* MESSAGES[] = {
    L"Ну потерпи ещё чуточку…",
    L"Загружаем тяжёлую артиллерию для PDF",
    L"Проверяем, не убежали ли ваши документы",
    L"Собираем пиксели в кучку",
    L"Почти готово. Не переключайтесь!",
    L"PDFTools просыпается. Кофе ему не предлагать!",
    L"Ещё немного — и можно работать!",
    L"Раскладываем ваши PDF по полочкам",
    L"УПС… задумались. Уже исправляем!",
    L"Солтех на связи. Наводим порядок!",
    L"Подготавливаем инструменты для работы",
    L"Сейчас всё будет красиво!"
};
static constexpr int MESSAGE_COUNT = sizeof(MESSAGES) / sizeof(MESSAGES[0]);
static HWND g_window = nullptr;
static HANDLE g_process = nullptr;
static DWORD g_processId = 0;
static ULONGLONG g_mainWindowFoundAt = 0;
static int g_message = 0;
static ULONG_PTR g_gdiplusToken = 0;
static std::wstring g_appPath;

static std::wstring ExeDirectory() {
    wchar_t path[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    std::wstring value(path);
    size_t slash = value.find_last_of(L"\\/");
    return slash == std::wstring::npos ? L"." : value.substr(0, slash);
}

static bool CALLBACK FindMainWindow(HWND hwnd, LPARAM) {
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid == g_processId && IsWindowVisible(hwnd) && GetWindow(hwnd, GW_OWNER) == nullptr) {
        g_mainWindowFoundAt = GetTickCount64();
        return FALSE;
    }
    return TRUE;
}

static void DrawTextBlock(Graphics& graphics, const wchar_t* text, REAL x, REAL y,
                          REAL width, REAL height, REAL size, COLORREF color, int style = FontStyleRegular) {
    FontFamily family(L"Segoe UI");
    Font font(&family, size, style, UnitPixel);
    SolidBrush brush(Color(255, GetRValue(color), GetGValue(color), GetBValue(color)));
    RectF rect(x, y, width, height);
    StringFormat format;
    format.SetAlignment(StringAlignmentNear);
    format.SetLineAlignment(StringAlignmentCenter);
    graphics.DrawString(text, -1, &font, rect, &format, &brush);
}

static void Paint(HWND hwnd) {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);
    RECT rc;
    GetClientRect(hwnd, &rc);
    const int width = rc.right, height = rc.bottom;
    HDC mem = CreateCompatibleDC(hdc);
    HBITMAP bitmap = CreateCompatibleBitmap(hdc, width, height);
    HGDIOBJ old = SelectObject(mem, bitmap);
    Graphics graphics(mem);
    graphics.SetSmoothingMode(SmoothingModeAntiAlias);
    graphics.Clear(Color(255, 23, 26, 33));

    SolidBrush sidebar(Color(255, 32, 37, 48));
    graphics.FillRectangle(&sidebar, 0, 0, 205, height);
    DrawTextBlock(graphics, L"PDFTools", 28, 28, 165, 45, 27, RGB(232,234,240), FontStyleBold);
    DrawTextBlock(graphics, L"РАБОЧЕЕ ПРОСТРАНСТВО", 29, 76, 170, 25, 11, RGB(156,167,184));
    DrawTextBlock(graphics, L"PDF", 29, 125, 165, 24, 13, RGB(53,111,229), FontStyleBold);
    DrawTextBlock(graphics, L"Подготовка запуска", 29, 153, 165, 36, 11, RGB(156,167,184));

    DrawTextBlock(graphics, L"Главная", 239, 27, width - 270, 42, 25, RGB(232,234,240), FontStyleBold);
    Pen divider(Color(255,57,67,85), 1.0f);
    graphics.DrawLine(&divider, 239, 82, width - 28, 82);
    DrawTextBlock(graphics, MESSAGES[g_message], 239, 104, width - 275, 105, 22, RGB(232,234,240), FontStyleBold);
    DrawTextBlock(graphics, L"Подготавливаем рабочее пространство PDFTools…", 239, height - 64, width - 275, 28, 12, RGB(156,167,184));

    BitBlt(hdc, 0, 0, width, height, mem, 0, 0, SRCCOPY);
    SelectObject(mem, old);
    DeleteObject(bitmap);
    DeleteDC(mem);
    EndPaint(hwnd, &ps);
}

static LRESULT CALLBACK WindowProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_PAINT: Paint(hwnd); return 0;
    case WM_TIMER:
        if (wParam == 1) {
            g_message = (g_message + 1 + (rand() % (MESSAGE_COUNT - 1))) % MESSAGE_COUNT;
            InvalidateRect(hwnd, nullptr, TRUE);
        } else if (wParam == 2 && g_process) {
            EnumWindows(FindMainWindow, 0);
            if (g_mainWindowFoundAt && GetTickCount64() - g_mainWindowFoundAt >= 2000) {
                KillTimer(hwnd, 2);
                DestroyWindow(hwnd);
                return 0;
            }
            DWORD code = 0;
            if (GetExitCodeProcess(g_process, &code) && code != STILL_ACTIVE && !g_mainWindowFoundAt) {
                KillTimer(hwnd, 2);
                MessageBoxW(hwnd, L"Не удалось запустить PDFToolsApp.exe. Проверьте файлы программы.", L"PDFTools", MB_ICONERROR | MB_OK);
                DestroyWindow(hwnd);
                return 0;
            }
        }
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wParam, lParam);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    srand((unsigned int)GetTickCount64());
    g_appPath = ExeDirectory();
    std::wstring appExe = g_appPath + L"\\PDFToolsApp.exe";
    if (GetFileAttributesW(appExe.c_str()) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(nullptr, L"Не найден PDFToolsApp.exe. Переустановите PDFTools целиком.", L"PDFTools", MB_ICONERROR | MB_OK);
        return 1;
    }

    GdiplusStartupInput gdiplusStartupInput;
    if (GdiplusStartup(&g_gdiplusToken, &gdiplusStartupInput, nullptr) != Ok) return 2;

    const wchar_t CLASS_NAME[] = L"PDFToolsNativeSplashWindow";
    WNDCLASSEXW wc = {};
    wc.cbSize = sizeof(wc);
    wc.hInstance = instance;
    wc.lpfnWndProc = WindowProc;
    wc.lpszClassName = CLASS_NAME;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = CreateSolidBrush(RGB(23,26,33));
    RegisterClassExW(&wc);

    const int width = 720, height = 280;
    int x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
    int y = (GetSystemMetrics(SM_CYSCREEN) - height) / 2;
    g_window = CreateWindowExW(WS_EX_TOPMOST, CLASS_NAME, L"PDFTools", WS_POPUP,
        x, y, width, height, nullptr, nullptr, instance, nullptr);
    ShowWindow(g_window, SW_SHOW);
    UpdateWindow(g_window);
    SetTimer(g_window, 1, 2600, nullptr);
    SetTimer(g_window, 2, 100, nullptr);

    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    std::wstring command = L"\"" + appExe + L"\"";
    if (!CreateProcessW(appExe.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr, g_appPath.c_str(), &si, &pi)) {
        MessageBoxW(g_window, L"Не удалось запустить основное приложение PDFTools.", L"PDFTools", MB_ICONERROR | MB_OK);
        DestroyWindow(g_window);
    } else {
        g_process = pi.hProcess;
        g_processId = pi.dwProcessId;
        CloseHandle(pi.hThread);
    }

    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    if (g_process) CloseHandle(g_process);
    if (wc.hbrBackground) DeleteObject(wc.hbrBackground);
    GdiplusShutdown(g_gdiplusToken);
    return 0;
}
