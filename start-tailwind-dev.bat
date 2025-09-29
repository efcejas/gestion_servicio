@echo off
echo 🚀 Iniciando modo desarrollo Tailwind CSS
echo.
echo 📁 Navegando a directorio theme/static_src...
cd theme\static_src

echo.
echo 🔨 Compilando CSS de Tailwind en modo desarrollo (watch + copy)...
echo ⚡ Los cambios se aplicarán automáticamente y se copiarán a static/css
echo 🛑 Presiona Ctrl+C para detener
echo.

npm run dev
