@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Building version.dll Proxy
echo ========================================
echo.

REM Check if CMake is installed
where cmake >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: CMake not found in PATH!
    echo.
    echo Please install CMake from: https://cmake.org/download/
    echo Make sure to check "Add CMake to system PATH" during installation
    echo.
    pause
    exit /b 1
)

echo CMake found: 
cmake --version | findstr /C:"cmake version"
echo.

REM Create build directory
if not exist build mkdir build
cd build

REM Try different Visual Studio generators
echo [1/3] Configuring with CMake...
echo Attempting to find Visual Studio...
echo.

REM Try VS 2026 first (if it exists)
cmake -G "Visual Studio 18 2026" -A x64 .. >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found: Visual Studio 2026
    set GENERATOR_FOUND=1
    goto :build
)

REM Try VS 2022
cmake -G "Visual Studio 17 2022" -A x64 .. >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found: Visual Studio 2022
    set GENERATOR_FOUND=1
    goto :build
)

REM Try VS 2019
cmake -G "Visual Studio 16 2019" -A x64 .. >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found: Visual Studio 2019
    set GENERATOR_FOUND=1
    goto :build
)

REM Try VS 2017
cmake -G "Visual Studio 15 2017" -A x64 .. >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found: Visual Studio 2017
    set GENERATOR_FOUND=1
    goto :build
)

REM Try NMake as fallback
cmake -G "NMake Makefiles" .. >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found: NMake Makefiles
    set GENERATOR_FOUND=1
    goto :build
)

echo ERROR: No suitable build system found!
echo.
echo Please install one of:
echo - Visual Studio 2022 (recommended)
echo - Visual Studio 2019
echo - Visual Studio 2017
echo - Build Tools for Visual Studio
echo.
echo Download from: https://visualstudio.microsoft.com/downloads/
echo.
cd ..
pause
exit /b 1

:build
echo.
echo [2/3] Building Release configuration...
cmake --build . --config Release
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    echo.
    echo Common issues:
    echo - Missing C++ compiler: Install "Desktop development with C++" in Visual Studio
    echo - Missing version.cpp: Make sure version.cpp is in the parent directory
    echo - Missing version.def: Make sure version.def is in the parent directory
    echo.
    cd ..
    pause
    exit /b 1
)

REM Copy output to parent directory
echo.
echo [3/3] Copying output files...

REM Check different possible output locations
if exist Release\version.dll (
    copy Release\version.dll ..\ >nul
) else if exist version.dll (
    copy version.dll ..\ >nul
) else (
    echo ERROR: Built DLL not found in expected location!
    echo Searching for DLL...
    dir /s /b version.dll
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ========================================
echo SUCCESS! version.dll created
echo ========================================
echo.
echo Files in current directory:
dir /b version.dll 2>nul
echo.
echo Next steps:
echo 1. Create allowed_cosmetics.json in this directory (example below)
echo 2. Copy version.dll to your game's executable directory
echo 3. Copy allowed_cosmetics.json to the same directory
echo 4. Launch the game
echo.
echo Example allowed_cosmetics.json:
echo {
echo     "bodyCharacteristic": [
echo         "Default.1",
echo         "Default.2",
echo         "Default.3"
echo     ]
echo }
echo.
pause