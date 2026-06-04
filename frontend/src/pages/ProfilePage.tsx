import { useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Spin, Tag, Typography, message } from "antd";
import { Activity, Bus, Home, Mail, Save, ShieldCheck, SunSnow, User, Wallet } from "lucide-react";
import { motion } from "framer-motion";
import {
  Cell,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { updateMe } from "../api/auth";
import { ApiError } from "../api/client";
import { fetchMyProfile, updateMyProfile } from "../api/profile";
import type { AccountUpdateRequest, UserProfileResponse, UserProfileUpdateRequest } from "../api/types";
import { useAuthStore } from "../store/auth";
import {
  accommodationOptions,
  budgetLevelOptions,
  defaultProfile,
  interestLabel,
  interestOptions,
  optionLabel,
  optionWeight,
  paceOptions,
  riskOptions,
  transportOptions,
  travelStyleOptions,
} from "../utils/profileOptions";

const { Title, Text, Paragraph } = Typography;

type AccountFormValues = {
  email?: string;
  current_password?: string;
  new_password?: string;
  confirm_password?: string;
};

const chartColors = ["#13c2c2", "#4da3ff", "#22c55e", "#ffb020", "#eb2f96", "#7c3aed"];

function profileWithDefaults(profile?: Partial<UserProfileUpdateRequest> | null): UserProfileUpdateRequest {
  return {
    ...defaultProfile,
    ...(profile ?? {}),
    interest_tags: profile?.interest_tags ?? defaultProfile.interest_tags ?? [],
  };
}

function buildRadarData(profile: UserProfileUpdateRequest) {
  const interests = new Set(profile.interest_tags ?? []);
  return [
    { subject: "预算", value: optionWeight(budgetLevelOptions, profile.budget_level), fullMark: 100 },
    { subject: "节奏", value: optionWeight(paceOptions, profile.pace_preference), fullMark: 100 },
    { subject: "天气规避", value: optionWeight(riskOptions, profile.risk_sensitivity), fullMark: 100 },
    { subject: "交通确定性", value: optionWeight(transportOptions, profile.transport_preference), fullMark: 100 },
    { subject: "住宿舒适度", value: optionWeight(accommodationOptions, profile.accommodation_preference), fullMark: 100 },
    { subject: "兴趣密度", value: Math.min(95, Math.max(30, interests.size * 12 + 35)), fullMark: 100 },
  ];
}

function buildPieData(profile: UserProfileUpdateRequest) {
  return [
    { name: "旅行风格", value: 1, detail: optionLabel(travelStyleOptions, profile.travel_style), label: "偏好的旅行方式" },
    { name: "预算倾向", value: 1, detail: optionLabel(budgetLevelOptions, profile.budget_level), label: "预算舒适区间" },
    { name: "交通偏好", value: 1, detail: optionLabel(transportOptions, profile.transport_preference), label: "路上怎么安排" },
    { name: "住宿偏好", value: 1, detail: optionLabel(accommodationOptions, profile.accommodation_preference), label: "住得是否顺手" },
    { name: "行程节奏", value: 1, detail: optionLabel(paceOptions, profile.pace_preference), label: "每天安排密度" },
    { name: "天气应对", value: 1, detail: optionLabel(riskOptions, profile.risk_sensitivity), label: "坏天气容忍度" },
  ];
}

function apiErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function ProfilePage() {
  const [profileForm] = Form.useForm<UserProfileUpdateRequest>();
  const [accountForm] = Form.useForm<AccountFormValues>();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);

  const profileQuery = useQuery({
    queryKey: ["profile", "me"],
    queryFn: fetchMyProfile,
  });

  const currentProfile = profileWithDefaults(profileQuery.data?.profile);
  const watchedProfile = profileWithDefaults(Form.useWatch([], profileForm) ?? currentProfile);

  useEffect(() => {
    if (profileQuery.data) {
      profileForm.setFieldsValue(profileWithDefaults(profileQuery.data.profile));
    }
  }, [profileForm, profileQuery.data]);

  useEffect(() => {
    if (user) {
      accountForm.setFieldsValue({ email: user.email });
    }
  }, [accountForm, user]);

  const saveProfileMutation = useMutation({
    mutationFn: updateMyProfile,
    onSuccess: (res: UserProfileResponse) => {
      profileForm.setFieldsValue(profileWithDefaults(res.profile));
      queryClient.setQueryData(["profile", "me"], res);
      message.success("旅行画像已保存，后续计划生成会读取这些偏好");
    },
    onError: (err) => {
      message.error(apiErrorMessage(err, "画像保存失败，请稍后重试"));
    },
  });

  const saveAccountMutation = useMutation({
    mutationFn: updateMe,
    onSuccess: (res) => {
      setUser(res);
      accountForm.setFieldsValue({ email: res.email, current_password: "", new_password: "", confirm_password: "" });
      message.success("账号信息已更新");
    },
    onError: (err) => {
      message.error(apiErrorMessage(err, "账号信息更新失败，请稍后重试"));
    },
  });

  const radarData = useMemo(() => buildRadarData(watchedProfile), [watchedProfile]);
  const pieData = useMemo(() => buildPieData(watchedProfile), [watchedProfile]);
  const summary = profileQuery.data?.profile_summary || "暂无画像摘要，保存一次画像后会生成完整偏好描述。";

  const handleSaveAccount = (values: AccountFormValues) => {
    const payload: AccountUpdateRequest = {};
    if (values.email && values.email !== user?.email) {
      payload.email = values.email;
    }
    if (values.new_password) {
      payload.current_password = values.current_password;
      payload.new_password = values.new_password;
    }
    if (!payload.email && !payload.new_password) {
      message.info("账号信息没有变化");
      return;
    }
    saveAccountMutation.mutate(payload);
  };

  return (
    <div style={{ maxWidth: 1240, margin: "0 auto", paddingBottom: 40 }}>
      <div style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>
            <Space>
              <User size={28} color="#13c2c2" />
              账号与旅行画像
            </Space>
          </Title>
          <Text type="secondary">这里维护的偏好会用于个性化生成旅行方案。</Text>
        </div>
        <Button
          type="primary"
          icon={<Save size={16} />}
          size="large"
          style={{ borderRadius: 8 }}
          onClick={() => profileForm.submit()}
          loading={saveProfileMutation.isPending}
        >
          保存画像
        </Button>
      </div>

      {profileQuery.isError ? <Alert type="warning" showIcon message="画像加载失败，当前显示默认值" style={{ marginBottom: 16 }} /> : null}

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={8}>
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
            <Card bordered={false} style={{ borderRadius: 8, marginBottom: 20 }}>
              <Title level={4} style={{ marginTop: 0 }}>
                <Space>
                  <Mail size={18} />
                  账号信息
                </Space>
              </Title>
              <Form<AccountFormValues> form={accountForm} layout="vertical" requiredMark={false} onFinish={handleSaveAccount}>
                <Form.Item name="email" label="邮箱" rules={[{ required: true, message: "请输入邮箱" }, { type: "email", message: "请输入有效邮箱" }]}>
                  <Input placeholder="you@example.com" autoComplete="email" />
                </Form.Item>
                <Form.Item name="current_password" label="当前密码">
                  <Input.Password placeholder="修改密码时必填" autoComplete="current-password" />
                </Form.Item>
                <Form.Item name="new_password" label="新密码" rules={[{ min: 6, message: "新密码至少 6 位" }]}>
                  <Input.Password placeholder="不修改可留空" autoComplete="new-password" />
                </Form.Item>
                <Form.Item
                  name="confirm_password"
                  label="确认新密码"
                  dependencies={["new_password"]}
                  rules={[
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        const next = getFieldValue("new_password");
                        if (!next || value === next) return Promise.resolve();
                        return Promise.reject(new Error("两次输入的新密码不一致"));
                      },
                    }),
                  ]}
                >
                  <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
                </Form.Item>
                <Button block icon={<ShieldCheck size={16} />} loading={saveAccountMutation.isPending} htmlType="submit">
                  保存账号信息
                </Button>
              </Form>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <Card bordered={false} style={{ borderRadius: 8 }}>
              <Title level={4} style={{ marginTop: 0 }}>画像摘要</Title>
              <Paragraph style={{ color: "#4b5563", marginBottom: 16 }}>{summary}</Paragraph>
              <Space wrap>
                {(watchedProfile.interest_tags ?? []).map((tag) => (
                  <Tag key={tag} color="cyan" style={{ borderRadius: 8, padding: "4px 10px" }}>
                    {interestLabel(tag)}
                  </Tag>
                ))}
              </Space>
            </Card>
          </motion.div>
        </Col>

        <Col xs={24} lg={16}>
          <Spin spinning={profileQuery.isLoading}>
            <Card bordered={false} style={{ borderRadius: 8, marginBottom: 20 }}>
              <Title level={4} style={{ marginTop: 0 }}>偏好设置</Title>
              <Form<UserProfileUpdateRequest>
                form={profileForm}
                layout="vertical"
                requiredMark={false}
                initialValues={currentProfile}
                onFinish={(values) => saveProfileMutation.mutate(profileWithDefaults(values))}
              >
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="travel_style" label="旅行风格" rules={[{ required: true, message: "请选择旅行风格" }]}>
                      <Select options={travelStyleOptions} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="budget_level" label="预算倾向" rules={[{ required: true, message: "请选择预算倾向" }]}>
                      <Select options={budgetLevelOptions} />
                    </Form.Item>
                  </Col>
                  <Col xs={24}>
                    <Form.Item name="interest_tags" label="兴趣标签">
                      <Select mode="tags" options={interestOptions} tokenSeparators={[",", "，"]} placeholder="选择或输入兴趣标签" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="transport_preference" label="交通偏好" rules={[{ required: true, message: "请选择交通偏好" }]}>
                      <Select options={transportOptions} suffixIcon={<Bus size={16} />} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="accommodation_preference" label="住宿偏好" rules={[{ required: true, message: "请选择住宿偏好" }]}>
                      <Select options={accommodationOptions} suffixIcon={<Home size={16} />} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="pace_preference" label="行程节奏" rules={[{ required: true, message: "请选择行程节奏" }]}>
                      <Select options={paceOptions} suffixIcon={<Activity size={16} />} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="risk_sensitivity" label="天气风险敏感度" rules={[{ required: true, message: "请选择天气风险敏感度" }]}>
                      <Select options={riskOptions} suffixIcon={<SunSnow size={16} />} />
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </Card>
          </Spin>

          <Row gutter={[20, 20]}>
            <Col xs={24} xl={12}>
              <Card bordered={false} style={{ borderRadius: 8, height: "100%" }}>
                <Title level={4} style={{ marginTop: 0 }}>偏好雷达</Title>
                <div style={{ height: 310 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: "#637083", fontSize: 12 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                      <Radar dataKey="value" stroke="#13c2c2" fill="#13c2c2" fillOpacity={0.28} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </Col>
            <Col xs={24} xl={12}>
              <Card bordered={false} style={{ borderRadius: 8, height: "100%" }}>
                <Title level={4} style={{ marginTop: 0 }}>偏好速览</Title>
                <div style={{ height: 250 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} innerRadius={56} outerRadius={82} paddingAngle={4} dataKey="value">
                        {pieData.map((_, index) => (
                          <Cell key={index} fill={chartColors[index % chartColors.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(_, __, item) => {
                          const payload = item.payload as { detail: string; name: string };
                          return [payload.detail, payload.name];
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <Space wrap>
                  {pieData.map((item, index) => (
                    <Tag key={item.name} color="default" style={{ borderRadius: 8, borderColor: chartColors[index], color: "#172033" }}>
                      {item.label}: {item.detail}
                    </Tag>
                  ))}
                </Space>
              </Card>
            </Col>
          </Row>

          <Card bordered={false} style={{ borderRadius: 8, marginTop: 20, background: "#f6f8fb" }}>
            <Space wrap size={[12, 12]}>
              <Tag icon={<Wallet size={14} />} color="green">预算: {optionLabel(budgetLevelOptions, watchedProfile.budget_level)}</Tag>
              <Tag icon={<Bus size={14} />} color="blue">交通: {optionLabel(transportOptions, watchedProfile.transport_preference)}</Tag>
              <Tag icon={<Home size={14} />} color="purple">住宿: {optionLabel(accommodationOptions, watchedProfile.accommodation_preference)}</Tag>
              <Tag icon={<Activity size={14} />} color="orange">节奏: {optionLabel(paceOptions, watchedProfile.pace_preference)}</Tag>
              <Tag icon={<SunSnow size={14} />} color="red">天气: {optionLabel(riskOptions, watchedProfile.risk_sensitivity)}</Tag>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
