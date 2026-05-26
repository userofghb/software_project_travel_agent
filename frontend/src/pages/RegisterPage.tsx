import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Checkbox, Col, Form, Input, Radio, Row, Select, Space, Steps, Typography } from "antd";
import { ArrowLeft, Compass, LogIn, Sparkles, UserPlus } from "lucide-react";
import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { fetchMe, login, register } from "../api/auth";
import { ApiError } from "../api/client";
import type { RegisterRequest } from "../api/types";
import { useAuthStore } from "../store/auth";

type RegisterFormValues = {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  travel_style: string;
  budget_level: string;
  interest_tags: string[];
  transport_preference: string;
  accommodation_preference: string;
  risk_sensitivity: string;
  pace_preference: string;
};

const interestOptions = [
  "历史人文",
  "自然风光",
  "本地美食",
  "城市漫步",
  "摄影打卡",
  "亲子友好",
  "博物馆",
  "购物休闲",
  "户外运动",
];

const selectOptions = {
  style: [
    { label: "休闲放松", value: "休闲放松" },
    { label: "深度文化", value: "深度文化" },
    { label: "美食探索", value: "美食探索" },
    { label: "自然户外", value: "自然户外" },
    { label: "高效打卡", value: "高效打卡" },
  ],
  transport: [
    { label: "公共交通优先", value: "公共交通优先" },
    { label: "步行友好", value: "步行友好" },
    { label: "打车优先", value: "打车优先" },
    { label: "自驾优先", value: "自驾优先" },
  ],
  accommodation: [
    { label: "舒适酒店", value: "舒适酒店" },
    { label: "精品民宿", value: "精品民宿" },
    { label: "高端酒店", value: "高端酒店" },
    { label: "经济实用", value: "经济实用" },
  ],
  pace: [
    { label: "轻松慢游", value: "轻松慢游" },
    { label: "张弛有度", value: "张弛有度" },
    { label: "安排充实", value: "安排充实" },
    { label: "高强度打卡", value: "高强度打卡" },
  ],
};

function toPayload(values: RegisterFormValues): RegisterRequest {
  return {
    username: values.username,
    email: values.email,
    password: values.password,
    profile: {
      travel_style: values.travel_style,
      budget_level: values.budget_level,
      interest_tags: values.interest_tags,
      transport_preference: values.transport_preference,
      accommodation_preference: values.accommodation_preference,
      risk_sensitivity: values.risk_sensitivity,
      pace_preference: values.pace_preference,
    },
  };
}

function authErrorMessage(err: unknown) {
  return err instanceof ApiError ? err.message : "注册失败，请稍后重试";
}

export function RegisterPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [error, setError] = useState<string | null>(null);

  const initialValues = useMemo<Partial<RegisterFormValues>>(
    () => ({
      travel_style: "休闲放松",
      budget_level: "中等预算",
      interest_tags: ["本地美食", "城市漫步"],
      transport_preference: "公共交通优先",
      accommodation_preference: "舒适酒店",
      risk_sensitivity: "中等敏感",
      pace_preference: "张弛有度",
    }),
    [],
  );

  const mutation = useMutation({
    mutationFn: async (values: RegisterFormValues) => {
      await register(toPayload(values));
      const token = await login({ username: values.username, password: values.password });
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
            创建你的旅行画像
          </Typography.Title>
          <Typography.Paragraph style={{ color: "rgba(255,255,255,.72)", fontSize: 16, maxWidth: 420 }}>
            注册时填写偏好，Agent 会在生成路线、酒店、预算和天气规避方案时优先参考这些信息。
          </Typography.Paragraph>
        </div>

        <Steps
          direction="vertical"
          current={1}
          items={[
            { title: "账号信息", description: "用于登录和保存方案" },
            { title: "旅行画像", description: "用于个性化生成路线" },
            { title: "自动登录", description: "注册完成后进入工作台" },
          ]}
          style={{ color: "#fff" }}
        />
      </section>

      <main style={{ display: "grid", placeItems: "center", padding: 32 }}>
        <Card style={{ width: "100%", maxWidth: 760, borderRadius: 12, boxShadow: "0 18px 48px rgba(0,21,41,.10)" }} bordered={false}>
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
              <div>
                <Typography.Title level={2} style={{ marginBottom: 8 }}>
                  注册账号
                </Typography.Title>
                <Typography.Text type="secondary">账号和画像会写入真实数据库，可直接用于后续规划。</Typography.Text>
              </div>
              <Button icon={<ArrowLeft size={16} />} onClick={() => navigate("/login", { state: location.state })}>
                返回登录
              </Button>
            </div>

            {error ? <Alert type="error" showIcon message={error} /> : null}

            <Form<RegisterFormValues>
              layout="vertical"
              requiredMark={false}
              initialValues={initialValues}
              onFinish={(values) => {
                setError(null);
                mutation.mutate(values);
              }}
            >
              <Row gutter={16}>
                <Col xs={24} md={8}>
                  <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }, { min: 3, message: "用户名至少 3 个字符" }]}>
                    <Input size="large" placeholder="例如 alice" autoComplete="username" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={16}>
                  <Form.Item name="email" label="邮箱" rules={[{ required: true, message: "请输入邮箱" }, { type: "email", message: "请输入有效邮箱" }]}>
                    <Input size="large" placeholder="alice@example.com" autoComplete="email" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }, { min: 6, message: "密码至少 6 位" }]}>
                    <Input.Password size="large" placeholder="至少 6 位" autoComplete="new-password" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="confirmPassword"
                    label="确认密码"
                    dependencies={["password"]}
                    rules={[
                      { required: true, message: "请再次输入密码" },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue("password") === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error("两次输入的密码不一致"));
                        },
                      }),
                    ]}
                  >
                    <Input.Password size="large" placeholder="再次输入密码" autoComplete="new-password" />
                  </Form.Item>
                </Col>
              </Row>

              <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0 18px" }}>
                <Sparkles size={18} color="#13c2c2" />
                <Typography.Title level={4} style={{ margin: 0 }}>
                  用户画像
                </Typography.Title>
              </div>

              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="travel_style" label="旅行风格" rules={[{ required: true, message: "请选择旅行风格" }]}>
                    <Select size="large" options={selectOptions.style} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="pace_preference" label="行程节奏" rules={[{ required: true, message: "请选择行程节奏" }]}>
                    <Select size="large" options={selectOptions.pace} />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="budget_level" label="预算倾向" rules={[{ required: true, message: "请选择预算倾向" }]}>
                    <Radio.Group optionType="button" buttonStyle="solid">
                      <Radio.Button value="经济实用">经济实用</Radio.Button>
                      <Radio.Button value="中等预算">中等预算</Radio.Button>
                      <Radio.Button value="高品质">高品质</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="interest_tags" label="兴趣标签" rules={[{ required: true, message: "请选择至少一个兴趣标签" }]}>
                    <Checkbox.Group options={interestOptions} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="transport_preference" label="交通偏好" rules={[{ required: true, message: "请选择交通偏好" }]}>
                    <Select size="large" options={selectOptions.transport} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="accommodation_preference" label="住宿偏好" rules={[{ required: true, message: "请选择住宿偏好" }]}>
                    <Select size="large" options={selectOptions.accommodation} />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="risk_sensitivity" label="天气风险敏感度" rules={[{ required: true, message: "请选择天气风险敏感度" }]}>
                    <Radio.Group optionType="button" buttonStyle="solid">
                      <Radio.Button value="不敏感">不敏感</Radio.Button>
                      <Radio.Button value="中等敏感">中等敏感</Radio.Button>
                      <Radio.Button value="高度敏感">高度敏感</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </Col>
              </Row>

              <Button type="primary" htmlType="submit" block size="large" loading={mutation.isPending} icon={<UserPlus size={18} />}>
                创建账号并进入工作台
              </Button>
            </Form>

            <div style={{ display: "flex", justifyContent: "center" }}>
              <Button type="link" icon={<LogIn size={16} />} onClick={() => navigate("/login", { state: location.state })}>
                已有账号，直接登录
              </Button>
            </div>
          </Space>
        </Card>
      </main>
    </div>
  );
}
