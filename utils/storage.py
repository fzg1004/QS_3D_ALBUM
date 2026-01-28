import os
import xml.etree.ElementTree as ET
from werkzeug.utils import secure_filename
from config import Config

class StorageManager:
    """Manage per-user storage layout under DATA_DIR.

    Layout:
      DATA_DIR/username/
        models.xml            -- index of model files (relative paths)
        imageFolder1/
            image.jpg
            image.ply
        imageFolder2/
            ...

    Methods operate on paths relative to the user's dir.
    """

    INDEX_NAME = 'models.xml'

    def __init__(self, data_dir):
        self.data_dir = data_dir

    def user_dir(self, username):
        return os.path.abspath(os.path.join(self.data_dir, username))

    def ensure_user(self, username):
        ud = self.user_dir(username)
        os.makedirs(ud, exist_ok=True)
        # ensure index exists
        idx = os.path.join(ud, self.INDEX_NAME)
        if not os.path.exists(idx):
            root = ET.Element('models')
            tree = ET.ElementTree(root)
            tree.write(idx, encoding='utf-8', xml_declaration=True)
        return ud

    def index_path(self, username):
        return os.path.join(self.user_dir(username), self.INDEX_NAME)

    def list_models(self, username):
        """Return list of model entries: dicts with 'relpath' and 'name' and 'url' """
        idx = self.index_path(username)
        models = []
        if not os.path.exists(idx):
            return models
        try:
            tree = ET.parse(idx)
            root = tree.getroot()
            for m in root.findall('model'):
                path = m.get('path')
                name = m.get('name') or os.path.basename(path)
                url = m.get('url')
                models.append({'relpath': path, 'name': name, 'url': url})
        except ET.ParseError:
            return []
        return models

    def add_model(self, username, relpath, model_url, display_name=None):
        """Add a model entry (relpath is like image1/image1.ply)"""
        ud = self.ensure_user(username)
        idx = self.index_path(username)
        tree = ET.parse(idx)
        root = tree.getroot()
        # avoid duplicates
        for m in root.findall('model'):
            if m.get('path') == relpath:
                return
        el = ET.SubElement(root, 'model')
        el.set('path', relpath)
        
        #增加一个下载地址
        el.set('url', model_url)
        
        if display_name:
            el.set('name', display_name)
            
        tree.write(idx, encoding='utf-8', xml_declaration=True)

    def remove_model(self, username, relpath):
        idx = self.index_path(username)
        if not os.path.exists(idx):
            return False
        tree = ET.parse(idx)
        root = tree.getroot()
        removed = False
        for m in root.findall('model'):
            if m.get('path') == relpath:
                root.remove(m)
                removed = True
        if removed:
            tree.write(idx, encoding='utf-8', xml_declaration=True)
        return removed

    def rename_model(self, username, old_relpath, new_base_name):
        """Rename a model file (only change base name, keep extension and folder).
        new_base_name should not include extension.
        Returns new_relpath or raises.
        """
        ud = self.user_dir(username)
        old_full = os.path.abspath(os.path.join(ud, old_relpath))
        if not old_full.startswith(ud + os.sep):
            raise ValueError('非法路径')
        if not os.path.exists(old_full):
            raise FileNotFoundError('源文件不存在')

        folder = os.path.dirname(old_full)
        old_name = os.path.basename(old_full)
        # preserve extension (supports .ply.gz)
        lower = old_name.lower()
        if lower.endswith('.ply.gz'):
            ext = '.ply.gz'
            base_old = old_name[:-7]
        else:
            base_old, ext = os.path.splitext(old_name)

        new_name = secure_filename(new_base_name) + ext
        new_full = os.path.join(folder, new_name)
        if os.path.exists(new_full):
            raise FileExistsError('目标已存在')
        os.rename(old_full, new_full)
        # update index
        old_rel = os.path.relpath(old_full, ud).replace('\\', '/')
        new_rel = os.path.relpath(new_full, ud).replace('\\', '/')
        self.remove_model(username, old_rel)
        self.add_model(username, new_rel)
        return new_rel

    def save_image(self, username, file_storage, original_name):
        """Save uploaded FileStorage into a new image-folder under user dir.
        Returns (folder_relpath, image_filename, image_fullpath)
        """
        ud = self.ensure_user(username)
        orig = original_name; #secure_filename(file_storage.filename)
        base = os.path.splitext(orig)[0]
        # create unique folder name
        folder_name = secure_filename(base)
        folder = os.path.join(ud, folder_name)
        i = 1
        while os.path.exists(folder):
            folder = os.path.join(ud, f"{folder_name}_{i}")
            i += 1
        os.makedirs(folder, exist_ok=True)
        image_path = os.path.join(folder, orig)
        file_storage.save(image_path)
        rel_folder = os.path.relpath(folder, ud).replace('\\', '/')
        return rel_folder, orig, image_path

    def get_full_path(self, username, relpath):
        ud = self.user_dir(username)
        full = os.path.abspath(os.path.join(ud, relpath))
        if not full.startswith(ud + os.sep):
            raise ValueError('非法路径')
        return full
