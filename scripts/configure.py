"""Create ignored local configuration without printing secrets or overwriting existing files."""

from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        print(f"Preserved existing {path.relative_to(ROOT)}")
        return
    path.write_text(text, encoding="utf-8")
    print(f"Created {path.relative_to(ROOT)} (secrets are not displayed)")


def main() -> None:
    jwt_secret = secrets.token_hex(32)
    postgres_password = secrets.token_hex(24)
    root_config = (ROOT / ".env.example").read_text(encoding="utf-8")
    root_config = root_config.replace("replace-with-at-least-32-random-characters", jwt_secret)
    root_config = root_config.replace("replace-with-a-long-random-password", postgres_password)
    write_if_missing(ROOT / ".env", root_config)
    local_config = (ROOT / "backend/.env.example").read_text(encoding="utf-8")
    local_config = local_config.replace("development-only-change-this-secret-before-deployment", jwt_secret)
    write_if_missing(ROOT / "backend/.env", local_config)
    print("Set OPENAI_API_KEY in the chosen .env to enable real AI. Email submission stays disabled.")


if __name__ == "__main__":
    main()
