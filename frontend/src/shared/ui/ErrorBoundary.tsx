import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("UI error boundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return <div style={{ padding: 24 }}>Произошла ошибка интерфейса. Перезагрузите страницу.</div>;
    }
    return this.props.children;
  }
}
