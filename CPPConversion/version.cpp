#include <windows.h>
#include <thread>
#include <mutex>
#include <map>
#include <set>
#include <string>
#include <fstream>
#include <sstream>
#include <deque>
#include <algorithm>
#include <filesystem>
#include <chrono>

// Simple JSON parser (no external dependencies)
#include <vector>

namespace fs = std::filesystem;

// ===================== CONFIG =====================
const wchar_t* CACHED_SKINS_DIR = L"D:\\Hytale\\install\\release\\package\\game\\latest\\Client\\UserData\\CachedPlayerSkins";
const char* ALLOWED_VALUES_JSON = "allowed_cosmetics.json";

const int WRITE_QUIET_MS = 600;
const int RECONCILE_DELAY_MS = 80;
const int HEATMAP_WINDOW = 10;
const int HEATMAP_ESCALATE_AMBER = 3;
const int HEATMAP_ESCALATE_RED = 6;
const int POLL_INTERVAL_MS = 200;

// ===================== SIMPLE JSON PARSER =====================
class SimpleJSON {
public:
    std::map<std::string, std::string> obj;
    std::map<std::string, std::set<std::string>> allowedKeyValues;

    static std::string trim(const std::string& str) {
        size_t start = str.find_first_not_of(" \t\n\r\"");
        size_t end = str.find_last_not_of(" \t\n\r\",");
        return (start == std::string::npos) ? "" : str.substr(start, end - start + 1);
    }

    bool loadFromFile(const std::string& path) {
        std::ifstream f(path);
        if (!f.is_open()) return false;
        std::stringstream buffer;
        buffer << f.rdbuf();
        std::string content = buffer.str();
        return parseObject(content, obj);
    }

    bool loadAllowedValues(const std::string& path) {
        std::ifstream f(path);
        if (!f.is_open()) return false;
        std::stringstream buffer;
        buffer << f.rdbuf();
        std::string content = buffer.str();
        
        // Parse outer object
        size_t pos = 0;
        while (pos < content.length()) {
            size_t keyStart = content.find('"', pos);
            if (keyStart == std::string::npos) break;
            size_t keyEnd = content.find('"', keyStart + 1);
            if (keyEnd == std::string::npos) break;
            
            std::string key = content.substr(keyStart + 1, keyEnd - keyStart - 1);
            
            size_t arrayStart = content.find('[', keyEnd);
            if (arrayStart == std::string::npos) break;
            size_t arrayEnd = content.find(']', arrayStart);
            if (arrayEnd == std::string::npos) break;
            
            std::string arrayContent = content.substr(arrayStart + 1, arrayEnd - arrayStart - 1);
            std::set<std::string> values;
            
            size_t vPos = 0;
            while (vPos < arrayContent.length()) {
                size_t vStart = arrayContent.find('"', vPos);
                if (vStart == std::string::npos) break;
                size_t vEnd = arrayContent.find('"', vStart + 1);
                if (vEnd == std::string::npos) break;
                
                values.insert(arrayContent.substr(vStart + 1, vEnd - vStart - 1));
                vPos = vEnd + 1;
            }
            
            allowedKeyValues[key] = values;
            pos = arrayEnd + 1;
        }
        
        return !allowedKeyValues.empty();
    }

    bool parseObject(const std::string& content, std::map<std::string, std::string>& out) {
        size_t pos = content.find('{');
        if (pos == std::string::npos) return false;
        
        while (pos < content.length()) {
            size_t keyStart = content.find('"', pos);
            if (keyStart == std::string::npos) break;
            size_t keyEnd = content.find('"', keyStart + 1);
            if (keyEnd == std::string::npos) break;
            
            std::string key = content.substr(keyStart + 1, keyEnd - keyStart - 1);
            
            size_t colon = content.find(':', keyEnd);
            size_t valueStart = content.find('"', colon);
            if (valueStart == std::string::npos) break;
            size_t valueEnd = content.find('"', valueStart + 1);
            if (valueEnd == std::string::npos) break;
            
            std::string value = content.substr(valueStart + 1, valueEnd - valueStart - 1);
            out[key] = value;
            
            pos = valueEnd + 1;
        }
        
        return !out.empty();
    }

    std::string toString() {
        std::ostringstream oss;
        oss << "{\n";
        bool first = true;
        for (auto& [key, val] : obj) {
            if (!first) oss << ",\n";
            oss << "    \"" << key << "\": \"" << val << "\"";
            first = false;
        }
        oss << "\n}";
        return oss.str();
    }
};

// ===================== SKIN EDITOR LOGIC =====================
class SkinEditor {
private:
    std::wstring skinPath;
    SimpleJSON skinData;
    SimpleJSON allowedValues;
    std::map<std::string, std::string> desiredCosmetics;
    std::map<std::string, std::deque<int>> conflictHistory;
    
    FILETIME lastWriteTime;
    std::chrono::steady_clock::time_point lastWriteSeenAt;
    bool reconcileScheduled = false;
    std::mutex mtx;

    std::wstring getNewestSkinFile() {
        std::wstring newest;
        FILETIME newestTime = {0, 0};
        
        for (const auto& entry : fs::directory_iterator(CACHED_SKINS_DIR)) {
            if (entry.path().extension() == L".json") {
                WIN32_FILE_ATTRIBUTE_DATA attr;
                if (GetFileAttributesExW(entry.path().c_str(), GetFileExInfoStandard, &attr)) {
                    if (CompareFileTime(&attr.ftLastWriteTime, &newestTime) > 0) {
                        newestTime = attr.ftLastWriteTime;
                        newest = entry.path().wstring();
                    }
                }
            }
        }
        return newest;
    }

    FILETIME getFileWriteTime(const std::wstring& path) {
        WIN32_FILE_ATTRIBUTE_DATA attr;
        if (GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &attr)) {
            return attr.ftLastWriteTime;
        }
        return {0, 0};
    }

    std::string wstringToString(const std::wstring& wstr) {
        if (wstr.empty()) return std::string();
        int size = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, nullptr, 0, nullptr, nullptr);
        std::string str(size - 1, 0);
        WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, &str[0], size, nullptr, nullptr);
        return str;
    }

    void atomicWrite(const std::wstring& path, const std::string& content) {
        std::wstring tmpPath = path + L".tmp";
        std::ofstream f(tmpPath, std::ios::binary);
        if (f.is_open()) {
            f << content;
            f.close();
            MoveFileExW(tmpPath.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING);
        }
    }

    bool loadSkinData() {
        std::string path = wstringToString(skinPath);
        return skinData.loadFromFile(path);
    }

public:
    SkinEditor() {
        // Load allowed values
        if (!allowedValues.loadAllowedValues(ALLOWED_VALUES_JSON)) {
            OutputDebugStringA("[SkinEditor] WARNING: Could not load allowed_cosmetics.json\n");
        }

        skinPath = getNewestSkinFile();
        if (skinPath.empty()) {
            OutputDebugStringA("[SkinEditor] ERROR: No skin files found\n");
            return;
        }

        if (!loadSkinData()) {
            OutputDebugStringA("[SkinEditor] ERROR: Could not load skin data\n");
            return;
        }

        lastWriteTime = getFileWriteTime(skinPath);
        lastWriteSeenAt = std::chrono::steady_clock::now();

        // Initialize desired cosmetics from current skin data
        for (auto& [key, value] : skinData.obj) {
            if (allowedValues.allowedKeyValues.count(key)) {
                desiredCosmetics[key] = value;
            }
        }

        OutputDebugStringA("[SkinEditor] Initialized successfully\n");
    }

    void setDesiredValue(const std::string& key, const std::string& value) {
        std::lock_guard<std::mutex> lock(mtx);
        
        if (!allowedValues.allowedKeyValues.count(key)) return;
        if (!allowedValues.allowedKeyValues[key].count(value)) return;
        
        desiredCosmetics[key] = value;
        requestReconcile();
    }

    void requestReconcile() {
        reconcileScheduled = true;
    }

    void pollFile() {
        std::lock_guard<std::mutex> lock(mtx);
        
        FILETIME currentWriteTime = getFileWriteTime(skinPath);
        
        if (CompareFileTime(&currentWriteTime, &lastWriteTime) != 0) {
            lastWriteTime = currentWriteTime;
            lastWriteSeenAt = std::chrono::steady_clock::now();
            
            if (!loadSkinData()) return;
            
            // Detect conflicts
            std::vector<std::string> conflicts;
            for (auto& [key, desired] : desiredCosmetics) {
                if (skinData.obj.count(key) && skinData.obj[key] != desired) {
                    conflicts.push_back(key);
                }
            }
            
            // Record conflict history
            for (auto& [key, desired] : desiredCosmetics) {
                bool hasConflict = std::find(conflicts.begin(), conflicts.end(), key) != conflicts.end();
                conflictHistory[key].push_back(hasConflict ? 1 : 0);
                if (conflictHistory[key].size() > HEATMAP_WINDOW) {
                    conflictHistory[key].pop_front();
                }
            }
            
            if (!conflicts.empty()) {
                OutputDebugStringA("[SkinEditor] Conflicts detected, requesting reconcile\n");
                requestReconcile();
            }
        }
        
        // Check if we should reconcile
        maybeReconcile();
    }

    void maybeReconcile() {
        if (!reconcileScheduled) return;
        
        auto now = std::chrono::steady_clock::now();
        auto quietMs = std::chrono::duration_cast<std::chrono::milliseconds>(now - lastWriteSeenAt).count();
        
        if (quietMs >= WRITE_QUIET_MS) {
            reconcileScheduled = false;
            Sleep(RECONCILE_DELAY_MS);
            reconcileNow();
        }
    }

    void reconcileNow() {
        // Merge desired cosmetics into skin data
        SimpleJSON merged;
        merged.obj = skinData.obj;
        
        for (auto& [key, value] : desiredCosmetics) {
            if (merged.obj.count(key) && allowedValues.allowedKeyValues.count(key)) {
                if (allowedValues.allowedKeyValues[key].count(value)) {
                    merged.obj[key] = value;
                }
            }
        }
        
        atomicWrite(skinPath, merged.toString());
        skinData = merged;
        lastWriteTime = getFileWriteTime(skinPath);
        lastWriteSeenAt = std::chrono::steady_clock::now();
        
        OutputDebugStringA("[SkinEditor] Reconciled to disk\n");
    }
};

// ===================== VERSION.DLL PROXY =====================
HMODULE hOriginalDll = nullptr;
SkinEditor* g_skinEditor = nullptr;

// Define function pointers for all version.dll exports
typedef BOOL (WINAPI *GetFileVersionInfoA_t)(LPCSTR, DWORD, DWORD, LPVOID);
typedef BOOL (WINAPI *GetFileVersionInfoW_t)(LPCWSTR, DWORD, DWORD, LPVOID);
typedef DWORD (WINAPI *GetFileVersionInfoSizeA_t)(LPCSTR, LPDWORD);
typedef DWORD (WINAPI *GetFileVersionInfoSizeW_t)(LPCWSTR, LPDWORD);
typedef BOOL (WINAPI *VerQueryValueA_t)(LPCVOID, LPCSTR, LPVOID*, PUINT);
typedef BOOL (WINAPI *VerQueryValueW_t)(LPCVOID, LPCWSTR, LPVOID*, PUINT);

GetFileVersionInfoA_t pGetFileVersionInfoA = nullptr;
GetFileVersionInfoW_t pGetFileVersionInfoW = nullptr;
GetFileVersionInfoSizeA_t pGetFileVersionInfoSizeA = nullptr;
GetFileVersionInfoSizeW_t pGetFileVersionInfoSizeW = nullptr;
VerQueryValueA_t pVerQueryValueA = nullptr;
VerQueryValueW_t pVerQueryValueW = nullptr;

// Export forwarding functions
extern "C" {
    __declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(LPCSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData) {
        return pGetFileVersionInfoA ? pGetFileVersionInfoA(lptstrFilename, dwHandle, dwLen, lpData) : FALSE;
    }

    __declspec(dllexport) BOOL WINAPI GetFileVersionInfoW(LPCWSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData) {
        return pGetFileVersionInfoW ? pGetFileVersionInfoW(lptstrFilename, dwHandle, dwLen, lpData) : FALSE;
    }

    __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR lptstrFilename, LPDWORD lpdwHandle) {
        return pGetFileVersionInfoSizeA ? pGetFileVersionInfoSizeA(lptstrFilename, lpdwHandle) : 0;
    }

    __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(LPCWSTR lptstrFilename, LPDWORD lpdwHandle) {
        return pGetFileVersionInfoSizeW ? pGetFileVersionInfoSizeW(lptstrFilename, lpdwHandle) : 0;
    }

    __declspec(dllexport) BOOL WINAPI VerQueryValueA(LPCVOID pBlock, LPCSTR lpSubBlock, LPVOID* lplpBuffer, PUINT puLen) {
        return pVerQueryValueA ? pVerQueryValueA(pBlock, lpSubBlock, lplpBuffer, puLen) : FALSE;
    }

    __declspec(dllexport) BOOL WINAPI VerQueryValueW(LPCVOID pBlock, LPCWSTR lpSubBlock, LPVOID* lplpBuffer, PUINT puLen) {
        return pVerQueryValueW ? pVerQueryValueW(pBlock, lpSubBlock, lplpBuffer, puLen) : FALSE;
    }
}

void SkinEditorThread() {
    while (g_skinEditor) {
        g_skinEditor->pollFile();
        Sleep(POLL_INTERVAL_MS);
    }
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        
        // Load the real version.dll from System32
        char systemPath[MAX_PATH];
        GetSystemDirectoryA(systemPath, MAX_PATH);
        strcat_s(systemPath, "\\version.dll");
        
        hOriginalDll = LoadLibraryA(systemPath);
        if (!hOriginalDll) {
            OutputDebugStringA("[version.dll] Failed to load original DLL\n");
            return FALSE;
        }
        
        // Get function pointers
        pGetFileVersionInfoA = (GetFileVersionInfoA_t)GetProcAddress(hOriginalDll, "GetFileVersionInfoA");
        pGetFileVersionInfoW = (GetFileVersionInfoW_t)GetProcAddress(hOriginalDll, "GetFileVersionInfoW");
        pGetFileVersionInfoSizeA = (GetFileVersionInfoSizeA_t)GetProcAddress(hOriginalDll, "GetFileVersionInfoSizeA");
        pGetFileVersionInfoSizeW = (GetFileVersionInfoSizeW_t)GetProcAddress(hOriginalDll, "GetFileVersionInfoSizeW");
        pVerQueryValueA = (VerQueryValueA_t)GetProcAddress(hOriginalDll, "VerQueryValueA");
        pVerQueryValueW = (VerQueryValueW_t)GetProcAddress(hOriginalDll, "VerQueryValueW");
        
        OutputDebugStringA("[version.dll] Proxy initialized\n");
        
        // Initialize skin editor
        g_skinEditor = new SkinEditor();
        
        // Start background thread
        std::thread(SkinEditorThread).detach();
        
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_skinEditor) {
            delete g_skinEditor;
            g_skinEditor = nullptr;
        }
        
        if (hOriginalDll) {
            FreeLibrary(hOriginalDll);
        }
    }
    
    return TRUE;
}