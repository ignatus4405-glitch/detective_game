# Assets — изображения

Заглушки генерируются кодом (цветовые аватары, градиенты). Для продакшена добавить:

- `icon.ico` — иконка exe (256x256, нуар-шляпа)
- `detective_*.png` — портреты 300x400
- `map_background.png` — стилизованная карта Блэквила
- `locations/*.jpg` — фоны локаций (бар, парк, участок)

Пока используется процедурная генерация в `main.py:draw_avatar`, `visual` градиенты.

Чтобы добавить реальную картинку:
1. Положи файл в `src/detective_game/assets/images/`
2. Загрузи в коде: `pygame.image.load(IMAGES_DIR / "my_image.png")`
3. Обнови `--add-data` в `tools/build.ps1` (уже покрывает всю папку `assets`)

