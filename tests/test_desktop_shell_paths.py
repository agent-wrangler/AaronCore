import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "shell" / "runtime_paths.js"


def _run_helper(expression: str):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not available")

    script = textwrap.dedent(
        f"""
        const helper = require({json.dumps(str(HELPER_PATH))});
        const result = {expression};
        console.log(JSON.stringify(result));
        """
    )
    completed = subprocess.run(
        [node, "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


class DesktopShellPathTests(unittest.TestCase):
    def test_packaged_installed_state_uses_user_home(self):
        resolved = _run_helper(
            """helper.resolveAaronCoreDataDir({
                homeDir: 'C:/Users/test',
                isPackaged: true,
                processExecPath: 'C:/Users/test/AppData/Local/Programs/aaroncore-desktop-runtime-35/AaronCore.exe',
                productSlug: 'aaroncore',
            })"""
        )
        self.assertEqual(resolved.replace("\\", "/"), "C:/Users/test/.aaroncore")

    def test_packaged_unpacked_state_stays_next_to_exe(self):
        resolved = _run_helper(
            """helper.resolveAaronCoreDataDir({
                homeDir: 'C:/Users/test',
                isPackaged: true,
                processExecPath: 'C:/Users/test/AaronCoreDesktop/win-unpacked/AaronCore.exe',
                productSlug: 'aaroncore',
            })"""
        )
        self.assertEqual(
            resolved.replace("\\", "/"),
            "C:/Users/test/AaronCoreDesktop/win-unpacked/Data",
        )

    def test_dev_shell_uses_appdata_for_repo_backed_state(self):
        resolved = _run_helper(
            """helper.resolveElectronUserDataDir({
                appDataDir: 'C:/Users/test/AppData/Roaming',
                isPackaged: false,
                dataDir: 'C:/Users/test/AaronCore',
                rootDir: 'C:/Users/test/AaronCore',
                processExecPath: 'C:/Users/test/AaronCore/desktop_runtime_35/node_modules/electron/dist/electron.exe',
                productName: 'AaronCore',
            })"""
        )
        self.assertEqual(
            resolved.replace("\\", "/"),
            "C:/Users/test/AppData/Roaming/AaronCore-dev-shell",
        )

    def test_packaged_installed_shell_uses_appdata_profile(self):
        resolved = _run_helper(
            """helper.resolveElectronUserDataDir({
                appDataDir: 'C:/Users/test/AppData/Roaming',
                isPackaged: true,
                dataDir: 'C:/Users/test/.aaroncore',
                rootDir: 'C:/Users/test/AppData/Local/Programs/aaroncore-desktop-runtime-35/resources/aaroncore',
                processExecPath: 'C:/Users/test/AppData/Local/Programs/aaroncore-desktop-runtime-35/AaronCore.exe',
                productName: 'AaronCore',
            })"""
        )
        self.assertEqual(
            resolved.replace("\\", "/"),
            "C:/Users/test/AppData/Roaming/AaronCore",
        )

    def test_explicit_user_data_dir_wins(self):
        resolved = _run_helper(
            """helper.resolveElectronUserDataDir({
                explicitUserDataDir: 'D:/Aaron/Profile',
                appDataDir: 'C:/Users/test/AppData/Roaming',
                isPackaged: true,
                dataDir: 'C:/Users/test/AaronCore',
                rootDir: 'C:/Users/test/AaronCore',
                processExecPath: 'C:/Users/test/AaronCoreDesktop/AaronCore.exe',
                productName: 'AaronCore',
            })"""
        )
        self.assertEqual(resolved.replace("\\", "/"), "D:/Aaron/Profile")

    def test_packaged_shell_with_repo_backed_state_still_uses_dev_profile_dir(self):
        resolved = _run_helper(
            """helper.resolveElectronUserDataDir({
                appDataDir: 'C:/Users/test/AppData/Roaming',
                isPackaged: true,
                dataDir: 'C:/Users/test/AaronCore',
                rootDir: 'C:/Users/test/AaronCore',
                processExecPath: 'C:/Users/test/AppData/Local/Programs/aaroncore-desktop-runtime-35/AaronCore.exe',
                productName: 'AaronCore',
            })"""
        )
        self.assertEqual(
            resolved.replace("\\", "/"),
            "C:/Users/test/AppData/Roaming/AaronCore-dev-shell",
        )

    def test_packaged_unpacked_shell_keeps_profile_next_to_exe(self):
        resolved = _run_helper(
            """helper.resolveElectronUserDataDir({
                appDataDir: 'C:/Users/test/AppData/Roaming',
                isPackaged: true,
                dataDir: 'C:/Users/test/AaronCoreDesktop/win-unpacked/Data',
                rootDir: 'C:/Users/test/AppData/Local/Programs/aaroncore-desktop-runtime-35/resources/aaroncore',
                portableExecutableDir: 'C:/Users/test/AaronCoreDesktop/win-unpacked',
                processExecPath: 'C:/Users/test/AaronCoreDesktop/win-unpacked/AaronCore.exe',
                productName: 'AaronCore',
            })"""
        )
        self.assertEqual(
            resolved.replace("\\", "/"),
            "C:/Users/test/AaronCoreDesktop/win-unpacked/Data/userData",
        )


if __name__ == "__main__":
    unittest.main()
