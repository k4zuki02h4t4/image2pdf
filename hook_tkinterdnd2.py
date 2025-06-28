# PyInstaller hook for tkinterdnd2
# This hook ensures that tkinterdnd2's binary files are included in the build

from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from tkinterdnd2 package
datas = collect_data_files('tkinterdnd2')

# Ensure tkdnd binaries are included
try:
    import tkinterdnd2
    import os
    
    tkdnd_path = os.path.join(os.path.dirname(tkinterdnd2.__file__), 'tkdnd')
    if os.path.exists(tkdnd_path):
        # Add all files in tkdnd directory
        for root, dirs, files in os.walk(tkdnd_path):
            for file in files:
                src_path = os.path.join(root, file)
                # Calculate relative path for destination
                rel_path = os.path.relpath(src_path, os.path.dirname(tkinterdnd2.__file__))
                dest_path = os.path.join('tkinterdnd2', rel_path)
                datas.append((src_path, os.path.dirname(dest_path)))
                
except ImportError:
    pass