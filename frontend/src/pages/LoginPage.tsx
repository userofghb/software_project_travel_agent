import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { Compass, LogIn, ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { fetchMe, login } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuthStore } from "../store/auth";

type LoginFormValues = {
  username: string;
  password: string;
};

function authErrorMessage(err: unknown) {
  return err instanceof ApiError ? err.message : "登录失败，请稍后重试";
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (values: LoginFormValues) => {
      const token = await login(values);
      const me = await fetchMe(token.access_token);
      return { token, me };
    },
    onSuccess: ({ token, me }) => {
      setSession(token.access_token, me);
      navigate((location.state as { from?: string } | null)?.from ?? "/");
    },
    onError: (err) => {
      setError(authErrorMessage(err));
    },
  });

  const goRegister = () => {
    navigate("/register", { state: location.state });
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #f0f7f7 0%, #eef5ff 48%, #f7fbff 100%)",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))",
      }}
    >
      <section
        style={{
          background: "#001529",
          color: "#fff",
          padding: "48px 44px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <Space align="center">
          <Compass size={34} color="#13c2c2" />
          <Typography.Title level={3} style={{ color: "#fff", margin: 0 }}>
            TravelOS
          </Typography.Title>
        </Space>

        <div>
          <Typography.Title level={1} style={{ color: "#fff", marginBottom: 16 }}>
            智能旅行工作台
          </Typography.Title>
          <Typography.Paragraph style={{ color: "rgba(255,255,255,.72)", fontSize: 16, maxWidth: 420 }}>
            登录后继续创建旅行方案、查看 Agent 生成进度、管理历史版本和个人旅行画像。
          </Typography.Paragraph>
        </div>

        <Space direction="vertical" size={14}>
          <Space>
            <ShieldCheck size={18} color="#13c2c2" />
            <span style={{ color: "rgba(255,255,255,.78)" }}>账号、方案和画像数据持久保存</span>
          </Space>
          <Space>
            <LogIn size={18} color="#13c2c2" />
            <span style={{ color: "rgba(255,255,255,.78)" }}>JWT 登录态自动用于后续接口请求</span>
          </Space>
        </Space>
      </section>

      <main style={{ display: "grid", placeItems: "center", padding: 32 }}>
        <Card style={{ width: "100%", maxWidth: 460, borderRadius: 12, boxShadow: "0 18px 48px rgba(0,21,41,.10)" }} bordered={false}>
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <div>
              <Typography.Title level={2} style={{ marginBottom: 8 }}>
                登录账号
              </Typography.Title>
              <Typography.Text type="secondary">使用你的账号进入旅行规划工作台。</Typography.Text>
            </div>

            {error ? <Alert type="error" showIcon message={error} /> : null}

            <Form<LoginFormValues>
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => {
                setError(null);
                mutation.mutate(values);
              }}
            >
              <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
                <Input size="large" placeholder="例如 alice" autoComplete="username" />
              </Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
                <Input.Password size="large" placeholder="请输入密码" autoComplete="current-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block size="large" loading={mutation.isPending} icon={<LogIn size={18} />}>
                登录
              </Button>
            </Form>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <Typography.Text type="secondary">还没有账号？</Typography.Text>
              <Button type="link" icon={<UserPlus size={16} />} onClick={goRegister}>
                创建账号并填写画像
              </Button>
            </div>
          </Space>
        </Card>
      </main>
    </div>
  );
}
