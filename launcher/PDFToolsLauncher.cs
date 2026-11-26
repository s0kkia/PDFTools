using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Windows.Forms;

internal sealed class SplashLauncher : Form
{
    private readonly string[] messages = new string[] {
        "Ну потерпи ещё чуточку…",
        "Загружаем тяжёлую артиллерию для PDF",
        "Проверяем, не убежали ли ваши документы",
        "Собираем пиксели в кучку",
        "Почти готово. Не переключайтесь!",
        "PDFTools просыпается. Кофе ему не предлагать!",
        "Ещё немного — и можно работать!",
        "Раскладываем ваши PDF по полочкам",
        "УПС… задумались. Уже исправляем!",
        "Солтех на связи. Наводим порядок!",
        "Подготавливаем инструменты для работы",
        "Сейчас всё будет красиво!"
    };

    private readonly Timer phraseTimer = new Timer();
    private readonly Timer pollTimer = new Timer();
    private readonly Timer closeTimer = new Timer();
    private readonly Random random = new Random();
    private Process appProcess;
    private string currentMessage;
    private bool splashClosed;

    public SplashLauncher()
    {
        Text = "PDFTools";
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = true;
        TopMost = true;
        ClientSize = new Size(900, 250);
        BackColor = Color.FromArgb(23, 26, 33);
        DoubleBuffered = true;

        currentMessage = messages[random.Next(messages.Length)];
        phraseTimer.Interval = 2600;
        phraseTimer.Tick += delegate {
            string next = currentMessage;
            while (next == currentMessage) next = messages[random.Next(messages.Length)];
            currentMessage = next;
            Invalidate();
        };

        pollTimer.Interval = 150;
        pollTimer.Tick += PollForMainWindow;

        closeTimer.Interval = 2000;
        closeTimer.Tick += delegate {
            closeTimer.Stop();
            splashClosed = true;
            Hide();
            TopMost = false;
        };

        Shown += delegate {
            phraseTimer.Start();
            try {
                string appPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "PDFToolsApp.exe");
                if (!File.Exists(appPath))
                    throw new FileNotFoundException("Не найден файл PDFToolsApp.exe", appPath);

                appProcess = Process.Start(new ProcessStartInfo {
                    FileName = appPath,
                    WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
                    UseShellExecute = true
                });
                pollTimer.Start();
            }
            catch (Exception ex) {
                phraseTimer.Stop();
                MessageBox.Show("Не удалось запустить PDFTools:\r\n" + ex.Message,
                    "PDFTools — ошибка запуска", MessageBoxButtons.OK, MessageBoxIcon.Error);
                Close();
            }
        };
    }

    private void PollForMainWindow(object sender, EventArgs e)
    {
        if (appProcess == null) return;
        try {
            appProcess.Refresh();
            if (appProcess.HasExited) {
                pollTimer.Stop();
                phraseTimer.Stop();
                Close();
                return;
            }

            if (!splashClosed && appProcess.MainWindowHandle != IntPtr.Zero && !closeTimer.Enabled) {
                closeTimer.Start();
            }
        }
        catch {
            // Process startup may briefly race with window creation.
        }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;

        using (SolidBrush background = new SolidBrush(Color.FromArgb(23, 26, 33)))
            g.FillRectangle(background, ClientRectangle);
        using (SolidBrush sidebar = new SolidBrush(Color.FromArgb(32, 37, 48)))
            g.FillRectangle(sidebar, 0, 0, 205, Height);
        using (Pen divider = new Pen(Color.FromArgb(57, 67, 85)))
            g.DrawLine(divider, 225, 25, 225, Height - 25);

        using (Font brand = new Font("Segoe UI", 23, FontStyle.Bold))
        using (SolidBrush text = new SolidBrush(Color.FromArgb(232, 234, 240)))
            g.DrawString("PDFTools", brand, text, 28, 37);
        using (Font small = new Font("Segoe UI", 9))
        using (SolidBrush muted = new SolidBrush(Color.FromArgb(156, 167, 184))) {
            g.DrawString("РАБОЧЕЕ ПРОСТРАНСТВО", small, muted, 29, 73);
            g.DrawString("Подготавливаем рабочее пространство PDFTools…", small, muted, 240, Height - 43);
        }
        using (Font nav = new Font("Segoe UI", 10, FontStyle.Bold))
        using (SolidBrush blue = new SolidBrush(Color.FromArgb(53, 111, 229)))
            g.DrawString("PDF", nav, blue, 30, 119);
        using (Font version = new Font("Segoe UI", 9))
        using (SolidBrush muted = new SolidBrush(Color.FromArgb(156, 167, 184)))
            g.DrawString("Запуск приложения", version, muted, 30, 145);

        using (Font heading = new Font("Segoe UI", 21, FontStyle.Bold))
        using (SolidBrush text = new SolidBrush(Color.FromArgb(232, 234, 240)))
            g.DrawString("Главная", heading, text, 240, 28);
        using (Pen line = new Pen(Color.FromArgb(57, 67, 85)))
            g.DrawLine(line, 240, 73, Width - 30, 73);

        using (Font phrase = new Font("Segoe UI", 18, FontStyle.Bold))
        using (SolidBrush text = new SolidBrush(Color.FromArgb(232, 234, 240))) {
            RectangleF rect = new RectangleF(240, 92, Width - 280, 100);
            g.DrawString(currentMessage, phrase, text, rect);
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        phraseTimer.Dispose();
        pollTimer.Dispose();
        closeTimer.Dispose();
        if (appProcess != null) appProcess.Dispose();
        base.OnFormClosed(e);
    }
}

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new SplashLauncher());
    }
}
