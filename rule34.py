import aiohttp
import asyncio
import aiofiles
import os
from datetime import datetime


class ImageDownloader:
    BASE_API_URL = 'https://api.rule34.xxx/index.php'

    def __init__(self, tags: str, num_images: int):
        self.tags = tags
        self.num_images = num_images
        date_str = datetime.now().strftime('%Y-%m-%d')
        self.folder_name = f"{tags.replace(':', ' ')}_{date_str}"
        self.pid = 0
        self.images_downloaded = 0
        self.images_required = 0
        self.semaphore = asyncio.Semaphore(10)

        if not os.path.exists(self.folder_name):
            os.makedirs(self.folder_name)

    def build_url(self, pid: int = 0) -> str:
        return f'{self.BASE_API_URL}?page=dapi&s=post&q=index&json=1&limit=100&tags={self.tags}&pid={pid}'

    async def fetch_json(self, session: aiohttp.ClientSession, url: str) -> dict:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        async with session.get(url, headers=headers) as response:
            if response.status == 403:
                print("Доступ запрещен. Возможно, ваш IP заблокирован или запрос требует авторизации.")
                return []

            if response.status != 200:
                print(f"Ошибка: Сервер вернул статус {response.status}")
                return []

            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return await response.json()
            else:
                print(f"Ошибка: Ожидался JSON, но получен {content_type}")
                return []

    async def download_image(self, session: aiohttp.ClientSession, url: str, filename: str, post_id: str):
        async with self.semaphore, session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(filename, mode='wb') as f:
                    await f.write(await response.read())
                    self.images_downloaded += 1
                    print(f'[{self.images_downloaded}/{self.num_images}] {post_id} downloaded successfully.')
                return True

        self.images_downloaded += 1
        print(f'[{self.images_downloaded}/{self.num_images}] {post_id} download failed.')
        return False

    async def run(self):
        async with aiohttp.ClientSession() as session:
            tasks = []
            results = []

            while self.images_required < self.num_images:
                json_response = await self.fetch_json(session, self.build_url(self.pid))

                if not json_response:
                    break  # Прекратить выполнение, если произошла ошибка при получении данных

                if isinstance(json_response, list):
                    posts = json_response
                else:
                    print('Unexpected response format. Exiting.')
                    break

                if not posts:
                    print('No more posts to process.')
                    break

                for post in posts:
                    if self.images_required >= self.num_images:
                        break

                    file_url = post.get('file_url')
                    if not file_url:
                        continue  # Пропустить, если нет URL файла

                    post_id = post.get('md5') or post.get('id')  # Используем md5 или id для имени файла
                    if not post_id:
                        continue  # Пропустить, если нет md5 или id

                    filename = os.path.join(self.folder_name, f"{post_id}.{file_url.split('.')[-1]}")
                    task = asyncio.create_task(self.download_image(session, file_url, filename, post_id))
                    tasks.append(task)
                    self.images_required += 1

                results = await asyncio.gather(*tasks)
                tasks = []
                self.pid += 1

            successful_downloads = sum(result for result in results if result)
            print(f'Successfully downloaded {successful_downloads} images.')


if __name__ == '__main__':
    num_images = int(input('Введите количество изображений для загрузки: '))
    tag_images = input('Введите теги: ')

    downloader = ImageDownloader(tag_images, num_images)
    asyncio.run(downloader.run())
