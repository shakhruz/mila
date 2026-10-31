#!/usr/bin/env python3
"""Прежний вход навыка: send_sticker.py <chat_id> <mood> [--reply-to <id>] [--force] — теперь scripts/sticker.py
(языковые паки; прежние mood greet/done/report/… переводятся в новые смыслы). Оставлен, чтобы старые вызовы не ломались."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import sticker  # noqa: E402

if __name__ == "__main__":
    sys.exit(sticker.main())
