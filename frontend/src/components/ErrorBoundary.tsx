import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, Result } from "antd";

interface Props {
  children: ReactNode;
  /** Optional fallback UI to show on error. When omitted a default Result is rendered. */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Top-level error boundary that catches rendering errors anywhere in the
 * component tree and shows a friendly fallback instead of a white screen.
 *
 * Clicking "Reload" performs a full page reload to recover from an
 * unrecoverable state.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to your monitoring service here.
    console.error("[ErrorBoundary]", error.message, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            minHeight: "100vh",
            padding: 24,
          }}
        >
          <Result
            status="error"
            title="页面出错了"
            subTitle={this.state.error?.message || "发生未知错误，请尝试刷新页面"}
            extra={[
              <Button type="primary" key="reload" onClick={this.handleReload}>
                刷新页面
              </Button>,
            ]}
          />
        </div>
      );
    }

    return this.props.children;
  }
}
