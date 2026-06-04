import React, { useState } from "react";
import { Typography, Card, Row, Col, Space, Tag, Input, Select, Button, Badge, Statistic, Drawer, Form, Popconfirm, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Wallet, Search, Filter, Activity, SunSnow, GitBranch, Trash2 } from "lucide-react";

import { listPlans, getPlanSummary, deletePlan } from "../api/plans";

const { Title, Text } = Typography;

export function PlanHistoryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = useState("");
  const [riskLevel, setRiskLevel] = useState("all");
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [durationRange, setDurationRange] = useState<string>("all");
  
  const { data: plans = [] } = useQuery({
    queryKey: ["plans", searchText, riskLevel],
    queryFn: () => listPlans({ search: searchText, risk_level: riskLevel }),
  });
  
  // 计算旅行天数
  const calculateDuration = (startDate: string, endDate: string): number => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
  };

  const filteredPlans = plans.filter((plan) => {
    const planYear = new Date(plan.start_date).getFullYear();
    if (selectedYear && planYear !== selectedYear) return false;

    if (durationRange !== "all") {
      const duration = calculateDuration(plan.start_date, plan.end_date);
      if (durationRange === "1-3" && !(duration >= 1 && duration <= 3)) return false;
      if (durationRange === "4-7" && !(duration >= 4 && duration <= 7)) return false;
      if (durationRange === "8-14" && !(duration >= 8 && duration <= 14)) return false;
      if (durationRange === "15+" && duration < 15) return false;
    }

    return true;
  });
  
  const { data: summaryMap = {} } = useQuery({
    queryKey: ["history-plan-summaries", filteredPlans.map((plan) => plan.id).join(",")],
    enabled: filteredPlans.length > 0,
    queryFn: async () => {
      const entries = await Promise.all(
        filteredPlans.map(async (plan) => {
          const summary = await getPlanSummary(plan.id);
          return [plan.id, summary] as const;
        }),
      );
      return Object.fromEntries(entries);
    },
  });

  const stats = [
    { title: "总生成方案", value: filteredPlans.length },
    { title: "已规划城市", value: new Set(filteredPlans.map((p) => p.city)).size },
    { title: "高风险预警", value: filteredPlans.filter((p) => summaryMap[p.id]?.risk_level === "high").length },
  ];
  
  // 获取可用的年份列表
  const availableYears = Array.from(new Set(plans.map((p) => new Date(p.start_date).getFullYear()))).sort().reverse();

  const deleteMutation = useMutation({
    mutationFn: (planId: number) => deletePlan(planId),
    onSuccess: async () => {
      message.success("方案已删除");
      await queryClient.invalidateQueries({ queryKey: ["plans"] });
      await queryClient.invalidateQueries({ queryKey: ["history-plan-summaries"] });
    },
    onError: (err: Error) => {
      message.error(err.message || "删除失败");
    },
  });

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", paddingBottom: 40 }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          <Space>
            <History size={28} color="#1890ff" />
            方案档案馆
          </Space>
        </Title>
        <Text type="secondary">查看、管理和回溯所有历史旅行方案与版本</Text>
      </div>

      <Row gutter={24} style={{ marginBottom: 24 }}>
        {stats.map((stat, idx) => (
          <Col xs={24} sm={8} key={idx}>
            <Card bordered={false} style={{ borderRadius: 12 }}>
              <Statistic title={stat.title} value={stat.value} valueStyle={{ color: "#1890ff", fontWeight: 600 }} />
            </Card>
          </Col>
        ))}
      </Row>

      <Card bordered={false} style={{ borderRadius: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
          <Space>
            <Input
              placeholder="搜索城市或方案名称..."
              prefix={<Search size={16} color="#bfbfbf" />}
              style={{ width: 250, borderRadius: 8 }}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
            <Button icon={<Filter size={16} />} onClick={() => setFilterDrawerOpen(true)}>筛选</Button>
          </Space>
        </div>

        <Row gutter={[24, 24]}>
          {filteredPlans.map((plan) => {
              const summary = summaryMap[plan.id];
              const risk = summary?.risk_level ?? "low";
              return (
                <Col xs={24} md={12} lg={8} key={plan.id}>
                  <Card hoverable style={{ borderRadius: 16, border: "1px solid #f0f0f0" }} onClick={() => navigate(`/plans/${plan.id}`)}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                      <div>
                        <Title level={4} style={{ margin: 0 }}>
                          {plan.title}
                        </Title>
                        <Space size="small" style={{ marginTop: 4 }}>
                          <Tag color="blue" style={{ borderRadius: 4 }}>
                            {formatVersion(plan.current_version?.version_no ?? null)}
                          </Tag>
                          <Text type="secondary" style={{ fontSize: 13 }}>
                            {formatPlanDateRange(plan.start_date, plan.end_date)}
                          </Text>
                        </Space>
                      </div>
                      <Badge status={risk === "high" ? "error" : risk === "medium" ? "warning" : "success"} />
                    </div>

                    <Space direction="vertical" style={{ width: "100%", marginBottom: 16 }}>
                      <div style={{ display: "flex", alignItems: "center", color: "#595959" }}>
                        <Wallet size={16} style={{ marginRight: 8, color: "#8c8c8c" }} />
                        <Text>预算 {typeof summary?.estimated_total === "number" ? `¥${summary.estimated_total}` : "—"}</Text>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", color: "#595959" }}>
                        <Activity size={16} style={{ marginRight: 8, color: "#8c8c8c" }} />
                        <Text>强度: {mapPace(summary?.pace ?? "relaxed")}</Text>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", color: "#595959" }}>
                        <SunSnow size={16} style={{ marginRight: 8, color: "#8c8c8c" }} />
                        <Text>天气风险: {mapRiskLevel(risk)}</Text>
                      </div>
                    </Space>

                    <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 16, display: "flex", justifyContent: "space-between" }}>
                      <Button
                        type="text"
                        size="small"
                        style={{ padding: 0, color: "#1890ff" }}
                        icon={<GitBranch size={14} />}
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/versions?planId=${plan.id}`);
                        }}
                      >
                        查看版本
                      </Button>
                      <Popconfirm
                        title="删除方案"
                        description="删除后将移除该方案及版本记录，无法恢复。"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          deleteMutation.mutate(plan.id);
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                      >
                        <Button
                          danger
                          type="text"
                          size="small"
                          icon={<Trash2 size={14} />}
                          loading={deleteMutation.isPending}
                          onClick={(e) => e.stopPropagation()}
                        >
                          删除
                        </Button>
                      </Popconfirm>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        更新于 {plan.updated_at.slice(0, 10)}
                      </Text>
                    </div>
                  </Card>
                </Col>
              );
            })}
        </Row>
      </Card>

      <Drawer
        title="高级筛选"
        placement="right"
        onClose={() => setFilterDrawerOpen(false)}
        open={filterDrawerOpen}
        width={400}
      >
        <Form layout="vertical">
          <Form.Item label="旅行年份">
            <Select 
              placeholder="选择年份" 
              value={selectedYear} 
              onChange={(value) => setSelectedYear(value)}
              allowClear
            >
              {availableYears.map((year) => (
                <Select.Option key={year} value={year}>
                  {year} 年
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="旅行天数">
            <Select value={durationRange} onChange={(value) => setDurationRange(value)}>
              <Select.Option value="all">全部天数</Select.Option>
              <Select.Option value="1-3">1-3 天（周末游）</Select.Option>
              <Select.Option value="4-7">4-7 天（一周游）</Select.Option>
              <Select.Option value="8-14">8-14 天（两周游）</Select.Option>
              <Select.Option value="15+">15+ 天（长期游）</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="风险等级">
            <Select value={riskLevel} onChange={(value) => setRiskLevel(value)}>
              <Select.Option value="all">全部风险等级</Select.Option>
              <Select.Option value="low">低风险</Select.Option>
              <Select.Option value="medium">中风险</Select.Option>
              <Select.Option value="high">高风险</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Button 
              type="primary" 
              onClick={() => setFilterDrawerOpen(false)}
              style={{ width: "100%" }}
            >
              确定
            </Button>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}

function mapRiskLevel(level: string): string {
  if (level === "high") return "高";
  if (level === "medium") return "中";
  if (level === "low") return "低";
  return level;
}

function mapPace(pace: string): string {
  if (pace === "intensive") return "紧凑";
  if (pace === "balanced") return "适中";
  if (pace === "relaxed") return "轻松";
  return pace;
}

function formatVersion(versionNo: number | null): string {
  if (versionNo == null) return "-";
  return `v${versionNo}`;
}

function formatPlanDateRange(startDate: string, endDate: string): string {
  if (!startDate && !endDate) return "-";
  if (!endDate || startDate === endDate) return startDate || endDate;
  return `${startDate} - ${endDate}`;
}
