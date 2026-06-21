import flet as ft
import yt_dlp
import asyncio
import os
import requests

# Настройки для 100% обхода ошибки 152 и 403
YDL_OPTIONS = {
    'quiet': True,
    'no_warnings': True,
    'extractor_args': {'youtube': {'player_client': ['android']}}, 
}

# Глобальная переменная для хранения выбранного пути
custom_download_path = None

def search_youtube(query: str, max_results: int = 50):
    """Поиск списка видео."""
    opts = dict(YDL_OPTIONS)
    opts['extract_flat'] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return result.get('entries', [])
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return []

def get_direct_urls_by_id_or_url(target: str):
    """Вытаскивает чистые ссылки и информацию о видео."""
    if target.startswith("http://") or target.startswith("https://"):
        url = target
    else:
        url = f"https://www.youtube.com/watch?v={target}"
        
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            title = info.get('title', 'Без названия')
            video_id = info.get('id', '')
            
            audio_url = None
            for f in info.get('formats', []):
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    audio_url = f.get('url')
                    break
            
            return video_url, (audio_url or video_url), title, video_id
        except Exception as e:
            print(f"Ошибка получения ссылок: {e}")
            return None, None, None, None

def get_final_path(filename: str):
    # Упрощенная логика: не лезем в реестр Windows
    if os.name == 'nt':
        # Твой текущий код для Windows оставь здесь, если хочешь
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            downloads_dir = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
    else:
        # Это путь для Android
        downloads_dir = '/storage/emulated/0/Download'
        
    # Создаем папку, если ее нет
    if not os.path.exists(downloads_dir):
        try:
            os.makedirs(downloads_dir, exist_ok=True)
        except:
            # Если нет доступа к основной папке, сохраняем в рабочую директорию приложения
            downloads_dir = os.getcwd()

    clean_name = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in ' .-_()']).strip()
    return os.path.join(downloads_dir, clean_name)

# --- Интерфейс Flet ---

async def main(page: ft.Page):
    page.title = "YouTube Player & Downloader"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 460
    page.window_height = 750
    page.padding = 15

    # --- Настройка FilePicker (Выбор папки) ---
    def on_folder_selected(e: ft.FilePickerResultEvent):
        global custom_download_path
        if e.path:
            custom_download_path = e.path
            path_text.value = f"Папка: ...{os.path.basename(e.path)}"
            page.snack_bar = ft.SnackBar(ft.Text(f"Папка изменена на: {e.path}"))
            page.snack_bar.open = True
            page.update()

    file_picker = ft.FilePicker(on_result=on_folder_selected)
    page.overlay.append(file_picker)

    # Строка настроек папки в самом верху
    path_text = ft.Text("Папка: Стандартная (Загрузки)", size=12, color=ft.colors.GREY_400, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    folder_btn = ft.IconButton(
        icon=ft.icons.FOLDER_OPEN, 
        icon_color=ft.colors.BLUE_200,
        tooltip="Выбрать папку для сохранения",
        on_click=lambda _: file_picker.get_directory_path()
    )
    
    folder_settings_row = ft.Row([path_text, folder_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # --- Функция скачивания ---
    async def download_file(target: str, media_type: str, title: str, button: ft.ElevatedButton):
        ext = ".mp3" if media_type == "audio" else ".mp4"
        
        button.disabled = True
        button.text = "Связь..."
        page.update()

        video_url, audio_url, fetched_title, _ = await asyncio.to_thread(get_direct_urls_by_id_or_url, target)
        stream_url = audio_url if media_type == "audio" else video_url
        final_title = title if title else (fetched_title or "youtube_media")
        
        save_path = get_final_path(f"{final_title}{ext}")

        if not stream_url:
            button.disabled = False
            button.text = "Скачать Аудио" if media_type == "audio" else "Скачать Видео"
            page.snack_bar = ft.SnackBar(ft.Text("YouTube отклонил запрос или ссылка неверна.", color=ft.colors.ERROR))
            page.snack_bar.open = True
            page.update()
            return

        button.text = "0%"
        page.update()

        def sync_download():
            try:
                response = requests.get(stream_url, stream=True, timeout=30)
                total_size = int(response.headers.get('content-length', 0))
                
                with open(save_path, 'wb') as file:
                    if total_size == 0:
                        file.write(response.content)
                    else:
                        downloaded = 0
                        for data in response.iter_content(chunk_size=1024 * 256):
                            downloaded += len(data)
                            file.write(data)
                            percent = int((downloaded / total_size) * 100)
                            button.text = f"{percent}%"
                            page.update()
                return True
            except Exception as e:
                print(f"Ошибка скачивания: {e}")
                return False

        success = await asyncio.to_thread(sync_download)
        
        button.disabled = False
        button.text = "Скачать Аудио" if media_type == "audio" else "Скачать Видео"
        
        if success:
            page.snack_bar = ft.SnackBar(ft.Text("Успешно сохранено!", color=ft.colors.GREEN))
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Ошибка при записи файла.", color=ft.colors.ERROR))
        
        page.snack_bar.open = True
        page.update()

    async def play_stream(video_id: str):
        page.snack_bar = ft.SnackBar(ft.Text("Открываем YouTube..."))
        page.snack_bar.open = True
        page.update()
        await page.launch_url(f"https://www.youtube.com/watch?v={video_id}")

    def create_video_card(title: str, video_id_or_url: str):
        btn_play = ft.ElevatedButton(text="Поток", icon=ft.icons.PLAY_ARROW, height=40)
        btn_video = ft.ElevatedButton(text="Скачать Видео", icon=ft.icons.DOWNLOAD, height=40, style=ft.ButtonStyle(color=ft.colors.BLUE_200))
        btn_audio = ft.ElevatedButton(text="Скачать Аудио", icon=ft.icons.MUSIC_NOTE, height=40, style=ft.ButtonStyle(color=ft.colors.GREEN_200))

        btn_play.on_click = lambda e: page.run_task(play_stream, video_id_or_url)
        btn_video.on_click = lambda e: page.run_task(download_file, video_id_or_url, "video", title, btn_video)
        btn_audio.on_click = lambda e: page.run_task(download_file, video_id_or_url, "audio", title, btn_audio)

        return ft.Card(
            elevation=4,
            content=ft.Container(
                padding=12,
                content=ft.Column([
                    ft.Text(title, weight=ft.FontWeight.BOLD, size=15, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=5),
                    ft.Row(controls=[btn_play, btn_video, btn_audio], spacing=8, wrap=True)
                ])
            )
        )

    # --- ВКЛАДКА 1: ПОИСК ---
    search_input = ft.TextField(hint_text="Введите запрос...", expand=True)
    loading_indicator_search = ft.ProgressRing(visible=False)
    results_view = ft.ListView(expand=True, spacing=15, padding=5)

    async def perform_search(e=None):
        if not search_input.value: return
        loading_indicator_search.visible = True
        results_view.controls.clear()
        page.update()

        results = await asyncio.to_thread(search_youtube, search_input.value)
        for video in results:
            if video and video.get('id'): 
                results_view.controls.append(create_video_card(video.get('title', 'Без названия'), video.get('id')))

        loading_indicator_search.visible = False
        page.update()

    search_btn = ft.IconButton(ft.icons.SEARCH, icon_size=30, on_click=lambda e: page.run_task(perform_search))
    search_input.on_submit = lambda e: page.run_task(perform_search)

    search_view_container = ft.Column([
        ft.Row([search_input, search_btn]),
        ft.Row([loading_indicator_search], alignment=ft.MainAxisAlignment.CENTER),
        results_view
    ], expand=True)

    # --- ВКЛАДКА 2: ПО ССЫЛКЕ ---
    url_input = ft.TextField(hint_text="Вставьте ссылку на видео или Shorts...", expand=True)
    loading_indicator_url = ft.ProgressRing(visible=False)
    url_card_holder = ft.Container()

    async def process_url_input(e=None):
        if not url_input.value: return
        loading_indicator_url.visible = True
        url_card_holder.content = None
        page.update()

        _, _, title, video_id = await asyncio.to_thread(get_direct_urls_by_id_or_url, url_input.value)
        
        loading_indicator_url.visible = False
        if title and video_id:
            url_card_holder.content = create_video_card(title, video_id)
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Не удалось распознать ссылку.", color=ft.colors.ERROR))
            page.snack_bar.open = True
            
        page.update()

    url_btn = ft.IconButton(ft.icons.ARROW_FORWARD, icon_size=30, on_click=lambda e: page.run_task(process_url_input))
    url_input.on_submit = lambda e: page.run_task(process_url_input)

    url_view_container = ft.Column([
        ft.Row([url_input, url_btn]),
        ft.Row([loading_indicator_url], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=10),
        url_card_holder
    ], visible=False, expand=True)

    # --- Переключатель вкладок ---
    def tabs_changed(e):
        if e.control.selected_index == 0:
            search_view_container.visible = True
            url_view_container.visible = False
        else:
            search_view_container.visible = False
            url_view_container.visible = True
        page.update()

    tabs = ft.Tabs(
        selected_index=0,
        on_change=tabs_changed,
        tabs=[
            ft.Tab(text="Поиск видео", icon=ft.icons.SEARCH_SHARP),
            ft.Tab(text="По ссылке", icon=ft.icons.LINK),
        ]
    )

    page.add(folder_settings_row, tabs, search_view_container, url_view_container)

ft.app(target=main)
