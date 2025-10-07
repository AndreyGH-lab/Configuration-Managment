import os
import getpass
import socket
import argparse
import platform

from vfs import VirtualFileSystem, VFSException


class ShellEmulator:
    def __init__(self, prompt_template="{user}@{host}:{cwd}$ ", vfs_path=None):
        self.user = getpass.getuser()
        self.host = socket.gethostname().split(".", 1)[0]
        self.home = os.path.expanduser("~")
        self.prompt_template = prompt_template
        self.running = True

        # VFS
        self.vfs = None
        if vfs_path:
            try:
                self.vfs = VirtualFileSystem(vfs_path)
                print(f"[INFO] VFS loaded successfully from {vfs_path}")
            except Exception as e:
                print(f"[ERROR] Failed to load VFS: {e}")
                self.vfs = None

        # current directory depends on mode
        self.cwd = "/" if self.vfs else os.getcwd()

    def _shorten_cwd(self, path: str) -> str:
        if not self.vfs:
            if path == self.home or path.startswith(self.home + os.sep):
                return path.replace(self.home, "~", 1)
        return path

    def format_prompt(self) -> str:
        cwd_display = self.vfs.cwd if self.vfs else self._shorten_cwd(self.cwd)
        return self.prompt_template.format(
            user=self.user, host=self.host, cwd=cwd_display
        )


    def parse_input(self, line: str):
        tokens = line.strip().split()
        if not tokens:
            return None, []
        return tokens[0], tokens[1:]


    def cmd_ls(self, args):
        if self.vfs:
            try:
                target = args[0] if args else None
                items = self.vfs.ls(target)
                print("  ".join(items))
            except VFSException as e:
                print(f"ls: {e}")
        else:
            print(f"[stub] ls called with args: {args}")

    def cmd_cd(self, args):
        if self.vfs:
            try:
                target = args[0] if args else "/"
                self.vfs.cd(target)
            except VFSException as e:
                print(f"cd: {e}")
        else:
            print(f"[stub] cd called with args: {args}")
            if not args:
                self.cwd = self.home
                print(f"(virtual) cwd -> {self.cwd}")
                return
            target = args[0]
            new = os.path.normpath(
                target if os.path.isabs(target)
                else os.path.join(self.cwd, target)
            )
            self.cwd = new
            print(f"(virtual) cwd -> {self.cwd}")

    def cmd_vfs_info(self, args):
        if not self.vfs:
            print("No VFS loaded.")
            return
        info = self.vfs.vfs_info()
        print(f"VFS file: {info['filename']}")
        print(f"SHA-256 : {info['sha256']}")

    def cmd_exit(self, args):
        print("Exiting emulator.")
        self.running = False

    def cmd_tree(self, args):
        if not self.vfs:
            print("No VFS loaded.")
            return
        path = args[0] if args else None
        try:
            print(self.vfs.tree(path))
        except VFSException as e:
            print(f"tree: {e}")

    def cmd_uname(self, args):
        system = platform.system()
        node = platform.node()
        release = platform.release()
        python_ver = platform.python_version()
        print(f"{system} {node} {release} Python/{python_ver}")

    def cmd_whoami(self, args):
        print(self.user)

    def run_command(self, cmd, args):
        try:
            if cmd == "exit":
                self.cmd_exit(args)
            elif cmd == "ls":
                self.cmd_ls(args)
            elif cmd == "cd":
                self.cmd_cd(args)
            elif cmd == "vfs-info":
                self.cmd_vfs_info(args)
            elif cmd == "tree":
                self.cmd_tree(args)
            elif cmd == "uname":
                self.cmd_uname(args)
            elif cmd == "whoami":
                self.cmd_whoami(args)
            else:
                print(f"Unknown command: {cmd!r}")
        except Exception as e:
            print(f"Error while executing command '{cmd}': {e}")

    def run_script(self, script_path):
        if not os.path.exists(script_path):
            print(f"[INFO] No startup script found ({script_path}), skipping.")
            return
        print(f"\n[INFO] Executing startup script: {script_path}\n")
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    print(f"{self.format_prompt()}{line}")
                    cmd, args = self.parse_input(line)
                    if cmd:
                        self.run_command(cmd, args)
                        if not self.running:
                            print("[INFO] Script terminated by 'exit' command.\n")
                            return
        except Exception as e:
            print(f"[ERROR] Failed to execute script '{script_path}': {e}")
        print("\n[INFO] Startup script execution finished.\n")

    def repl(self):
        try:
            while self.running:
                try:
                    line = input(self.format_prompt())
                except EOFError:
                    print()
                    break
                if not line.strip():
                    continue
                cmd, args = self.parse_input(line)
                if cmd:
                    self.run_command(cmd, args)
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting.")


def main():
    parser = argparse.ArgumentParser(
        description="Stage 3: Shell emulator with Virtual File System"
    )
    parser.add_argument("--vfs-path", help="Path to VFS CSV file", default=None)
    parser.add_argument("--prompt", help="Custom prompt template", default="{user}@{host}:{cwd}$ ")
    args = parser.parse_args()

    print("[DEBUG] Launch configuration:")
    print(f"  VFS path       : {args.vfs_path}")
    print(f"  Prompt template: {args.prompt!r}\n")

    # Если пользователь не указал путь, используем дефолтный CSV
    vfs_path = args.vfs_path or os.path.join(os.getcwd(), "vfs_nested.csv")

    emulator = ShellEmulator(prompt_template=args.prompt, vfs_path=vfs_path)

    startup_path = os.path.join(os.getcwd(), "startup.txt")
    emulator.run_script(startup_path)

    if emulator.running:
        emulator.repl()



if __name__ == "__main__":
    main()
