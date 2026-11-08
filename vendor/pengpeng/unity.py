"""本地 Unity 读取层。

沿用 Hermes 的 cards_map → CardDef → GUID catalog 思路，重新实现依赖解析和
有界资源包缓存。这里不加载 / 执行游戏程序集，不向游戏目录写入任何文件。
"""
from __future__ import annotations

import logging
import json
import re
from collections import OrderedDict, deque
from pathlib import Path

import UnityPy

from .common import guid
from .bundle import BundleDirectory, UnsupportedBundle

log = logging.getLogger(__name__)


class UnityReader:
    def __init__(self, root: Path, store, progress=lambda message, done, total: None):
        self.root = root / 'Data' / 'Win'
        self.store = store
        self.cache = OrderedDict()
        self.cabs = {r['name']: r['bundle'] for r in store.db.execute('SELECT * FROM cabs')}
        self.file_bundle = {}
        self.directories = {}
        UnityPy.config.FALLBACK_UNITY_VERSION = '6000.3.11f1'
        # 索引目录已由安装清单指纹隔离。热启动直接读取解析后的清单，
        # 避免每次解压所有语言的 manifest；不缓存 Unity 原生对象。
        cached = store.get_meta('manifest_v1')
        if cached:
            self.catalog, self.cards, self.dependencies, self.locales = cached
            progress('读取资源清单缓存', 1, 1)
            return
        manifests = list(self.root.glob('asset_manifest_*.unity3d'))
        progress('读取基础资源清单', 0, len(manifests) + 1)
        env = self.load('asset_manifest.unity3d')
        def read(suffix):
            return next(v.read_typetree() for k, v in env.container.items() if k.lower().endswith(suffix))
        catalog = read('/base_assets_catalog.asset')
        self.catalog = {a['guid']: catalog['m_bundleNames'][a['bundleId']] for a in catalog['m_assets']}
        mapping = read('/cards_map.asset')['map']
        self.cards = {k: guid(v) for k, v in zip(mapping['keys'], mapping['values'])}
        data = read('/bundle_deps.asset')
        names = data['allBundleNames']
        self.dependencies = {name: [names[i] for i in deps['allDependencies'] if names[i] != name]
                             for name, deps in zip(names, data['bundles'])}
        self.locales = {}
        for index, path in enumerate(manifests):
            progress('读取语言资源清单 · ' + path.stem, index + 1, len(manifests) + 1)
            locale = path.stem.removeprefix('asset_manifest_').lower()
            local = self.load(path.name)
            data = next(v.read_typetree() for k, v in local.container.items() if 'asset_catalog_locale_' in k)
            self.locales[locale] = {a['baseGuid']: (a['guid'], data['m_bundleNames'][a['bundleId']])
                                    for a in data['m_assets']}
        store.set_meta('manifest_v1', [self.catalog, self.cards, self.dependencies, self.locales])
        progress('资源清单就绪', len(manifests) + 1, len(manifests) + 1)
        log.info('资源清单：%s 张卡牌，%s 项基础资源，语言包 %s', len(self.cards), len(self.catalog), list(self.locales))

    def load(self, bundle):
        if bundle in self.cache:
            self.cache.move_to_end(bundle)
            return self.cache[bundle]
        base = self.root.parent.parent / 'Hearthstone_Data' if bundle.startswith('@player/') else self.root
        filename = bundle.removeprefix('@player/')
        path = (base / filename).resolve()
        if path.parent != base.resolve():
            raise ValueError('资源包路径必须位于 Data/Win 内')
        if not path.is_file():
            raise FileNotFoundError(f'本地未安装资源包：{bundle}')
        log.debug('读取资源包 %s (%.1f MB)', bundle, path.stat().st_size / 1048576)
        try:
            directory = self.directory(bundle, path)
            env = directory.environment()
            # 目录常驻，解压块只属于最近加载的环境，避免全索引缓存所有正文。
            directory.cache.clear()
        except UnsupportedBundle:
            env = UnityPy.load(str(path))
        def register(file):
            if isinstance(file, UnityPy.files.SerializedFile):
                name = Path(file.name).name.lower()
                self.cabs[name] = bundle
                self.file_bundle[name] = bundle
                return
            for sub in getattr(file, 'files', {}).values():
                register(sub)
        for file in env.files.values():
            register(file)
        self.cache[bundle] = env
        # 复杂皮肤会交错访问多个预制体。按需读取后可保留更大的元数据热集合，
        # 同时限制序列化数据总量；旧格式整包加载仍按大包计费、尽快淘汰。
        def weight(name):
            record = self.directories.get(name)
            return sum(size for _, _, size, flags in record[1].nodes if flags & 4) if record else 64 * 1024 * 1024
        while len(self.cache) > 1 and (len(self.cache) > 24 or sum(weight(name) for name in self.cache) > 64 * 1024 * 1024):
            old, _ = self.cache.popitem(last=False)
            if old in self.directories:
                self.directories[old][1].cache.clear()
        return env

    def directory(self, bundle, path=None):
        """只读压缩目录定位 CAB，首次找引用不再试着解压每个依赖包。"""
        path = path or self.root / bundle
        stat = path.stat()
        stamp = (stat.st_size, stat.st_mtime_ns)
        previous = self.directories.get(bundle)
        if previous is None or previous[0] != stamp:
            directory = BundleDirectory(path)
            self.directories[bundle] = (stamp, directory)
            for name, _, _, flags in directory.nodes:
                if flags & 4:
                    self.cabs[Path(name).name.lower()] = bundle
        return self.directories[bundle][1]

    def source_paths(self):
        """同时收录 AssetBundle 与 Unity Player 内置资源，避免遗漏界面音效。"""
        files = {p.name: p for p in self.root.glob('*.unity3d')}
        player = self.root.parent.parent / 'Hearthstone_Data'
        for path in player.iterdir():
            if path.is_file() and (path.suffix == '.assets' or path.name == 'globalgamemanagers'
                                    or re.fullmatch(r'level\d+', path.name)):
                files['@player/' + path.name] = path
        return files

    def resolve(self, ref, locale='zhcn'):
        key = guid(ref)
        bundle = self.catalog.get(key)
        actual_locale = 'global'
        if key in self.locales.get(locale, {}):
            key, bundle = self.locales[locale][key]
            actual_locale = locale
        if not bundle:
            raise KeyError(f'清单中没有资源：{ref}')
        env = self.load(bundle)
        if key not in env.container:
            raise KeyError(f'资源包缺少 GUID：{key} ({bundle})')
        return env.container[key].deref(), bundle, actual_locale

    def pointer(self, obj, ptr):
        """解析 PPtr，按 manifest 的 bundle_deps 查找外部 CAB，不按 pathID 猜测。"""
        pathid = ptr.get('m_PathID', 0)
        if not pathid:
            return None
        file = obj.assets_file
        fileid = ptr.get('m_FileID', 0)
        if fileid == 0:
            return file.objects.get(pathid)
        target = file.externals[fileid - 1].path.rsplit('/', 1)[-1].lower()
        # Unity 内建对象不在 AssetBundle 依赖清单中；扫描全部依赖也找不到。
        # 尤其默认粒子网格会反复命中这里，过去每次都解压大量无关资源包。
        if target in ('unity default resources', 'unity_builtin_extra'):
            raise FileNotFoundError(f'Unity 内建资源不在客户端资源包中：{target}')
        player_external = self.root.parent.parent / 'Hearthstone_Data' / target
        if target not in self.cabs and player_external.is_file() and player_external.suffix == '.assets':
            self.load('@player/' + target)
        if target not in self.cabs:
            owner = self.file_bundle.get(file.name.lower(), self.cabs.get(file.name.lower()))
            for dependency in self.dependencies.get(owner, []):
                if (self.root / dependency).exists():
                    try:
                        self.directory(dependency)
                    except UnsupportedBundle:
                        self.load(dependency)
                if target in self.cabs:
                    break
        if target not in self.cabs:
            raise FileNotFoundError(f'外部资源未安装或无法定位：{target}')
        env = self.load(self.cabs[target])
        # CAB + pathID 已是精确地址，不再为每条引用枚举全包对象。
        candidate_file = env.get_cab(target)
        if candidate_file is not None and hasattr(candidate_file, 'objects'):
            candidate = candidate_file.objects.get(pathid)
            if candidate is not None:
                return candidate
        raise KeyError(f'CAB 中没有对象 {pathid}: {target}')

