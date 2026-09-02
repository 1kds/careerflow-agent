from __future__ import annotations

import argparse
import os

from .agent import CareerFlowAgent
from .db import Database
from .tools import ToolRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="CareerFlow 취업 준비 에이전트")
    parser.add_argument("--db", default="careerflow.db", help="SQLite DB 경로")
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default=os.getenv("CAREERFLOW_PROVIDER", "openai"),
        help="모델 API 공급자",
    )
    parser.add_argument("--model", default=None, help="사용할 모델(생략하면 공급자별 기본값)")
    parser.add_argument("--trace", action="store_true", help="툴 호출 과정을 표시")
    args = parser.parse_args()

    registry = ToolRegistry(Database(args.db))
    try:
        agent = CareerFlowAgent(registry, model=args.model, provider=args.provider)
    except Exception as exc:
        parser.error(f"{args.provider} 클라이언트를 초기화할 수 없습니다: {exc}")
    print(f"CareerFlow입니다. provider={args.provider}. 종료하려면 /quit을 입력하세요.")
    while True:
        try:
            message = input("\n나> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if message in {"/quit", "/exit"}:
            break
        if not message:
            continue
        try:
            print(f"\nCareerFlow> {agent.run(message, trace=args.trace)}")
        except Exception as exc:
            print(f"\n오류> {exc}")


if __name__ == "__main__":
    main()
