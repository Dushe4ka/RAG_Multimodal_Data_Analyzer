"""Точка входа: python -m prod_deep_agent (из корня репо) или из prod_deep_agent: python -m app.cli."""
try:
    from prod_deep_agent.app.cli import main
except ImportError:
    from app.cli import main

if __name__ == "__main__":
    main()
