# Android Build Checklist y Guía de Prevención de Errores

Documento para evitar fallos futuros en compilaciones de APK para Android usando Buildozer.

---

## 🔴 Errores Detectados en PR #1

### Error 1: Missing `python-for-android` (p4a)
**Síntoma**: `FileNotFoundError: No such file or directory: '.buildozer/android/platform/python-for-android'`

**Causa**: El workflow ejecutaba `buildozer android clean` ANTES de que buildozer inicializara el entorno.

**Solución**:
- ❌ NO ejecutar `buildozer android clean` en el paso de setup
- ✅ Dejar que `buildozer android debug` maneje la inicialización completa
- ✅ Usar `buildozer android clean` solo DESPUÉS de una compilación exitosa

### Error 2: Missing Android SDK Build-Tools
**Síntoma**: `build-tools folder not found /home/runner/.buildozer/android/platform/android-sdk/build-tools`

**Causa**: El SDK no estaba siendo instalado explícitamente. Buildozer esperaba que existiera.

**Solución**:
- ✅ Descargar manualmente Android SDK Command-line Tools
- ✅ Usar `sdkmanager` para instalar componentes específicos:
  - `build-tools;34.0.0`
  - `platforms;android-34`
  - `ndk;25.2.9519653` (o la versión especificada en buildozer.spec)
- ✅ Aceptar todas las licencias: `yes | sdkmanager --licenses`
- ✅ Exportar `ANDROID_SDK_ROOT` para que buildozer encuentre las herramientas

### Error 3: Missing AIDL Tool
**Síntoma**: `Aidl not found, please install it.`

**Causa**: AIDL viene incluido en build-tools, pero no estaban siendo instaladas.

**Solución**: (Se resuelve con Error 2 - instalar build-tools explícitamente)

---

## ✅ Workflow Correcto para GitHub Actions

```yaml
name: Build APK

on:
  push:
    branches: [ "main", "apk-android" ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install system dependencies
        run: |
          sudo apt update
          sudo apt install -y \
            git zip unzip openjdk-17-jdk python3-pip \
            autoconf libtool pkg-config zlib1g-dev \
            libncurses5-dev libncursesw5-dev cmake \
            libffi-dev libssl-dev
          pip3 install --user buildozer cython

      - name: Download and Setup Android SDK
        run: |
          mkdir -p ~/.android
          touch ~/.android/repositories.cfg
          
          # Download Android SDK Command-line Tools
          mkdir -p ~/android-sdk
          cd ~/android-sdk
          wget -q https://dl.google.com/android/repository/commandlinetools-linux-10406996_latest.zip
          unzip -q commandlinetools-linux-10406996_latest.zip
          
          # Restructure for sdkmanager
          mkdir -p cmdline-tools/latest
          mv cmdline-tools/* cmdline-tools/latest/ 2>/dev/null || true
          
          # Set environment variables
          echo "ANDROID_SDK_ROOT=~/android-sdk" >> $GITHUB_ENV
          echo "ANDROID_HOME=~/android-sdk" >> $GITHUB_ENV
          echo "~/android-sdk/cmdline-tools/latest/bin" >> $GITHUB_PATH

      - name: Install Android SDK Components
        run: |
          export ANDROID_SDK_ROOT=~/android-sdk
          export PATH=$PATH:~/android-sdk/cmdline-tools/latest/bin
          
          # Accept licenses and install required components
          yes | sdkmanager --licenses 2>/dev/null || true
          sdkmanager "build-tools;34.0.0" "platforms;android-34" "ndk;25.2.9519653"

      - name: Build APK with Buildozer
        run: |
          export PATH=$PATH:~/.local/bin/
          export ANDROID_SDK_ROOT=~/android-sdk
          export ANDROID_HOME=~/android-sdk
          buildozer android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: virus-apk
          path: bin/*.apk
```

---

## 📋 Checklist Precompilación

### buildozer.spec
- [ ] `android.api` coincide con `platforms` en workflow (ej: api 34 → `platforms;android-34`)
- [ ] `android.build_tools` coincide con `build-tools` en workflow (ej: `build-tools;34.0.0`)
- [ ] `android.ndk` coincide con `ndk` en workflow (formato: `25c` → `ndk;25.2.9519653`)
- [ ] `android.minapi` es >= 21 (requerido para pygame)
- [ ] `requirements` incluye todas las librerías (pygame, hostpython3, etc.)
- [ ] `android.permissions` cubre necesidades de la app (INTERNET, STORAGE, etc.)
- [ ] `android.archs` especifica arquitectura (arm64-v8a es estándar)

### GitHub Actions Workflow
- [ ] NO ejecutar `buildozer android clean` en setup (solo después de compilación exitosa)
- [ ] Descargar SDK Command-line Tools explícitamente
- [ ] Instalar componentes específicos con `sdkmanager`
- [ ] Ejecutar `yes | sdkmanager --licenses` ANTES de instalar componentes
- [ ] Exportar variables de entorno:
  - `ANDROID_SDK_ROOT=~/android-sdk`
  - `ANDROID_HOME=~/android-sdk` (alternativa)
  - Agregar al `PATH`
- [ ] No usar `android.sdk` deprecated (algunos sistemas lo ignoran)

### Código Python
- [ ] Detectar plataforma Android: `sys.platform == "android"`
- [ ] Rutas de almacenamiento usando `os.environ.get('ANDROID_PRIVATE')`
- [ ] Pantalla sin SCALED flag en Android (usar `(0, 0), pygame.FULLSCREEN`)
- [ ] Controles táctiles (FINGERDOWN, FINGERMOTION, FINGERUP)
- [ ] No asumir mouse.set_visible() disponible en Android

### src/touch_input.py
- [ ] Zonas táctiles dentro de límites de pantalla
- [ ] Conversión de coordenadas normalizadas (0.0-1.0) a píxeles
- [ ] Manejo de múltiples dedos simultáneos (`fingers` dict)
- [ ] Iconos dibujados con offset relativo a rect position

---

## 🚨 Errores Comunes a Evitar

| Error | Causa | Prevención |
|-------|-------|-----------|
| Python-for-android no encontrado | `buildozer android clean` prematuramente | No limpiar en setup; dejar que buildozer inicialice |
| Build-tools no instaladas | SDK no descargado | Descargar Command-line Tools y usar `sdkmanager` |
| Licencias no aceptadas | No ejecutar `sdkmanager --licenses` | Ejecutar `yes \| sdkmanager --licenses` PRIMERO |
| NDK versión mismatch | `android.ndk` en spec no coincide con instalado | Verificar versión en workflow; descargar específica |
| Crash en Android sin permisos | Falta de permisos en spec | Agregar a `android.permissions` según necesidades |
| Crash al guardar datos | Ruta de almacenamiento incorrecta | Usar `ANDROID_PRIVATE` env var |
| Pantalla no se ve correctamente | Flag pygame.SCALED en Android | Usar `(0, 0), pygame.FULLSCREEN` en Android |
| Crash por falta de dependencias | `requirements` incompleto | Incluir todas: pygame, hostpython3, etc. |

---

## 📚 Recursos

- [Buildozer Documentation](https://buildozer.readthedocs.io/)
- [Python-for-Android](https://python-for-android.readthedocs.io/)
- [Android SDK Command-line Tools](https://developer.android.com/studio/command-line)
- [Pygame Android Support](https://pygame.readthedocs.io/en/latest/ref/pygame_android.html)

---

## 🔄 Próximos Pasos

1. ✅ Reemplazar workflow con versión correcta
2. ✅ Verificar buildozer.spec contra checklist
3. ✅ Ejecutar compilación en local antes de push (si es posible)
4. ✅ Mergear PR #1 después de validación
5. 📌 Crear rama de CI/CD stale para reparaciones futuras

---

**Última actualización**: 2026-06-13
**Estado**: Documento de referencia activo
