"""Updates carry the owner's seal (1.18.147; the owner, 2026-11-19: "how safe is the code that
makes up clean view? could someone use another ai chat to change it?", then "yes, label the
key so its obvious what it is"). An installed copy takes an update only when version.sig is
the owner's Ed25519 signature of version.json and every file it downloads has the fingerprint
version.json lists. Tests use a made-up key (sealing.TEST_SEED), never the owner's, and
nothing goes online: a stand-in urlopen, or a server on this PC."""
import functools
import http.server
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import support
import sealing
from sealing import sign_release
from test_own_exe import load_launcher

RFC_8032 = [   # secret, public, message, signature (RFC 8032 section 7.1, tests 1 and 2)
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e3970"
     "1cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613"
     "d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]


class TheSealItself(unittest.TestCase):
    def setUp(self):
        self.lm = load_launcher()

    def test_the_standard_examples(self):
        for sk, pk, msg, sig in RFC_8032:
            sk, pk, msg, sig = map(bytes.fromhex, (sk, pk, msg, sig))
            self.assertEqual(sign_release.public_of(sk, self.lm), pk)
            self.assertEqual(sign_release.sign(sk, msg, self.lm), sig)
            self.assertTrue(self.lm.ed25519_ok(pk, msg, sig))
            self.assertFalse(self.lm.ed25519_ok(pk, msg + b"!", sig))
            for i in (0, 31, 32, 63):
                bad = bytearray(sig)
                bad[i] ^= 1
                self.assertFalse(self.lm.ed25519_ok(pk, msg, bytes(bad)), i)
            self.assertFalse(self.lm.ed25519_ok(pk, msg, sig[:63]))

    def test_the_owners_public_key_is_a_real_one(self):
        self.assertNotEqual(self.lm.PUBLIC_KEY, bytes(32))
        self.assertIsNotNone(self.lm._ed_point(self.lm.PUBLIC_KEY))

    def test_the_key_file_says_what_it_is(self):
        text = sign_release.key_text(sealing.TEST_SEED, sign_release.public_of(sealing.TEST_SEED))
        self.assertTrue(text.startswith("CLEANVIEW UPDATE KEY  -  SECRET, DO NOT SHARE"))
        self.assertEqual(sign_release.KEY_FILE.name, "CleanView update key - SECRET.txt")
        for said in ("If it's lost", "Keep it secret", "Google Drive"):
            self.assertIn(said, text)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "key.txt"
            p.write_text(text, encoding="utf8")
            self.assertEqual(sign_release.read_key(p), sealing.TEST_SEED)

    def test_the_app_only_offers_a_sealed_update(self):
        src = (support.ROOT / "CleanView.pyw").read_text(encoding="utf8")
        self.assertIn("lm.remote_version(timeout=6)", src)


class AnInstalledCopy(unittest.TestCase):
    """What update() takes and what it turns down; nothing is swapped in when it turns one
    down, and CleanView carries on as it is."""

    def setUp(self):
        self.lm = load_launcher()
        sealing.use_test_key(self.lm)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.here = Path(self.tmp.name)
        (self.here / "version.json").write_text(json.dumps({"version": "1.0.0", "files": []}))
        (self.here / "CleanView.pyw").write_bytes(b"old = 1\n")
        self.files = {"CleanView.pyw": b"new = 2\n", "cvcore.py": b"x = 1\n", "words.json": b"{}"}
        self.remote = {"version": "1.0.1", "files": list(self.files)}
        self.served = {}
        self.serve()
        p = mock.patch.object(self.lm, "HERE", self.here)
        p.start()
        self.addCleanup(p.stop)

    def serve(self, seed=sealing.TEST_SEED):
        data, sig = sealing.sealed_release(self.lm, self.remote, self.files, seed)
        self.served = dict(self.files, **{"version.json": data, "version.sig": sig.encode()})

    def urlopen(self, url, timeout=None):
        import io
        import urllib.error
        name = url.rsplit("/", 1)[-1]
        if name not in self.served:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        r = io.BytesIO(self.served[name])
        return mock.MagicMock(__enter__=lambda s: r, __exit__=lambda s, *a: None)

    def update(self):
        with mock.patch.object(self.lm.urllib.request, "urlopen", self.urlopen):
            return self.lm.update()

    def turned_down(self):
        with self.assertRaises(Exception):
            self.update()
        self.assertEqual((self.here / "CleanView.pyw").read_bytes(), b"old = 1\n")
        self.assertFalse((self.here / "cvcore.py").exists())
        self.assertEqual(json.loads((self.here / "version.json").read_text())["version"], "1.0.0")

    def test_a_sealed_update_goes_in(self):
        self.assertEqual(self.update(), "1.0.1")
        for name, body in self.files.items():
            self.assertEqual((self.here / name).read_bytes(), body)
        kept = json.loads((self.here / "version.json").read_text())
        self.assertEqual(kept["version"], "1.0.1")
        self.assertIn("sha256", kept)

    def test_no_seal(self):
        del self.served["version.sig"]
        self.turned_down()

    def test_an_empty_or_garbled_seal(self):
        for sig in (b"", b"not a seal", b"00" * 64):
            self.served["version.sig"] = sig
            self.turned_down()

    def test_someone_elses_key(self):
        self.serve(seed=bytes(32))
        self.turned_down()

    def test_version_json_changed_after_the_seal(self):
        self.served["version.json"] = self.served["version.json"].replace(b"1.0.1", b"1.0.2")
        self.turned_down()

    def test_a_file_that_isnt_the_one_listed(self):
        self.served["cvcore.py"] = b"import os; os.system('bad')\n"
        self.turned_down()

    def test_a_file_without_a_fingerprint(self):
        remote = json.loads(self.served["version.json"])
        remote["files"].append("extra.py")
        self.files["extra.py"] = b"y = 1\n"
        self.remote = {"version": "1.0.1", "files": list(self.files)}
        data, sig = sealing.sealed_release(self.lm, self.remote, self.files)
        listed = json.loads(data)
        del listed["sha256"]["extra.py"]
        data = json.dumps(listed).encode()
        sig = sign_release.sign(sealing.TEST_SEED, self.lm.SEAL_FOR.encode() + data, self.lm)
        self.served.update({"extra.py": b"y = 1\n", "version.json": data,
                            "version.sig": sig.hex().encode()})
        self.turned_down()

    def test_another_apps_seal(self):
        data = self.served["version.json"]
        sig = sign_release.sign(sealing.TEST_SEED, b"CleanListen update\n" + data, self.lm)
        self.served["version.sig"] = sig.hex().encode()
        self.turned_down()

    def test_nothing_newer_is_left_alone(self):
        self.remote["version"] = "1.0.0"
        self.serve()
        self.assertIsNone(self.update())


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0,
                     "needs git")
class AWholeRelease(unittest.TestCase):
    """tools/sign_release.py seals a release in a git repo (staged copy, another chat's work
    in the working copy kept), check passes, and an installed copy downloads it over HTTP from
    a server on this PC and takes it; a file changed after the seal is turned down."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo, self.installed = root / "repo", root / "installed"
        self.repo.mkdir()
        self.installed.mkdir()
        lm = load_launcher()
        test_public = sign_release.public_of(sealing.TEST_SEED, lm).hex()
        launcher = (support.ROOT / "launcher.pyw").read_text(encoding="utf8").replace(
            lm.PUBLIC_KEY.hex(), test_public)
        self.release = {"launcher.pyw": launcher, "CleanView.pyw": "app = 2\n",
                        "cvcore.py": "core = 2\n"}
        for n, body in self.release.items():
            (self.repo / n).write_text(body, encoding="utf8", newline="\n")
        (self.repo / "version.json").write_text(json.dumps(
            {"version": "1.0.1", "files": list(self.release)}) + "\n", encoding="utf8")
        self.git("init", "-q")
        self.git("add", ".")
        key = root / "key.txt"
        key.write_text(sign_release.key_text(sealing.TEST_SEED, bytes.fromhex(test_public)),
                       encoding="utf8")
        # another chat's unfinished change in the working copy only
        (self.repo / "version.json").write_text(json.dumps(
            {"version": "1.0.1", "files": list(self.release) + ["unfinished.py"]}) + "\n")
        for name, value in (("REPO", self.repo), ("KEY_FILE", key)):
            p = mock.patch.object(sign_release, name, value)
            p.start()
            self.addCleanup(p.stop)
        with mock.patch("builtins.print"):
            sign_release.seal()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), "-c", "core.autocrlf=false", *args],
                              capture_output=True, check=True).stdout

    def serve_staged(self, out):
        """What raw GitHub would serve once this is pushed: the staged copy."""
        out.mkdir()
        for n in list(self.release) + ["version.json", "version.sig"]:
            (out / n).write_bytes(self.git("show", f":{n}"))
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(out)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/"

    def installed_copy(self, raw):
        (self.installed / "version.json").write_text(json.dumps({"version": "1.0.0", "files": []}))
        (self.installed / "CleanView.pyw").write_text("app = 1\n")
        lm = load_launcher()
        sealing.use_test_key(lm)
        return lm, mock.patch.multiple(lm, HERE=self.installed, RAW=raw)

    def test_sealed_checked_and_taken(self):
        staged = json.loads(self.git("show", ":version.json"))
        self.assertEqual(set(staged["sha256"]), set(self.release))
        self.assertNotIn("unfinished.py", staged["files"])
        kept = json.loads((self.repo / "version.json").read_text())
        self.assertIn("unfinished.py", kept["files"])            # the other chat's work kept
        self.assertEqual(kept["sha256"], staged["sha256"])
        with mock.patch("builtins.print"):
            sign_release.check()
        lm, here = self.installed_copy(self.serve_staged(Path(self.tmp.name) / "web"))
        with here:
            self.assertEqual(lm.update(), "1.0.1")
        for n, body in self.release.items():
            self.assertEqual((self.installed / n).read_text(encoding="utf8"), body)

    def test_a_file_changed_after_the_seal(self):
        (self.repo / "cvcore.py").write_text("core = 3\n")
        self.git("add", "cvcore.py")
        with self.assertRaises(ValueError), mock.patch("builtins.print"):
            sign_release.check()
        lm, here = self.installed_copy(self.serve_staged(Path(self.tmp.name) / "web"))
        with here, self.assertRaises(lm.NotSealed):
            lm.update()
        self.assertEqual((self.installed / "CleanView.pyw").read_text(), "app = 1\n")


if __name__ == "__main__":
    unittest.main()
