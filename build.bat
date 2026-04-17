# Windows build script for the C++ DNS Resolver
# Requires g++ from MSYS2 / MinGW-w64 in PATH.
# Install MSYS2 from https://www.msys2.org/ then:  pacman -S mingw-w64-ucrt-x86_64-gcc

@echo off
setlocal

set SRC=core\dns_resolver.cpp
set OUT=core\dns_resolver.exe
set FLAGS=-std=c++17 -O2 -Wall -Wextra

echo [1/2] Checking for g++...
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: g++ not found.  Install MSYS2 and run: pacman -S mingw-w64-ucrt-x86_64-gcc
    exit /b 1
)

echo [2/2] Compiling %SRC% ...
g++ %FLAGS% %SRC% -o %OUT% -lws2_32

if %errorlevel% equ 0 (
    echo.
    echo Build SUCCESS: %OUT%
    echo.
    echo Test it:
    echo   %OUT% google.com A
) else (
    echo Build FAILED.
    exit /b 1
)
