cmake_minimum_required(VERSION 3.15)
project(VersionDllProxy)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Create the DLL
add_library(version SHARED
    version.cpp
    version.def
)

# Link against required Windows libraries
target_link_libraries(version PRIVATE
    shlwapi
)

# Set output name to exactly "version.dll"
set_target_properties(version PROPERTIES
    OUTPUT_NAME "version"
    PREFIX ""
    SUFFIX ".dll"
)

# Optimization flags for release
if(MSVC)
    target_compile_options(version PRIVATE
        $<$<CONFIG:Release>:/O2 /GL>
    )
    target_link_options(version PRIVATE
        $<$<CONFIG:Release>:/LTCG>
    )
endif()

# Output build information
message(STATUS "Configuring version.dll proxy")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")