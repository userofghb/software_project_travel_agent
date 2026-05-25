import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Typography, Card, Row, Col, Space, Tag, Timeline, Divider, Button, Alert, Spin, Empty, message } from "antd";
import { useSearchParams } from "react-router-dom";
import { listPlanVersions, restorePlanVersion, getPlanSummary } from "../api/plans";
import type { TripPlanVersionResponse } from "../api/types";
import { mockVersionHistory } from "../utils/mockData";
import { GitMerge, GitCommit, User, Bot, TrendingDown, TrendingUp, Plus, Minus, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";

const { Title, Text } = Typography;

type LegacyMock = (typeof mockVersionHistory)[number];

type UiVersion = {
  id: number;
  version: string;
  source: string;
  createdAtText: string;
  summary: string;
  raw: TripPlanVersionResponse;
};

export function VersionHistoryPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const planIdNumber = Number(searchParams.get("planId"));
  const validPlanId = Number.isFinite(planIdNumber) && planIdNumber > 0;
  const [activeVersionId, setActiveVersionId] = useState<number | null>(null);

  const versionsQuery = useQuery({
    queryKey: ["plan-versions", planIdNumber],
    queryFn: () => listPlanVersions(planIdNumber),
    enabled: validPlanId,
  });

  const summaryQuery = useQuery({
    queryKey: ["plan-summary", planIdNumber],
    queryFn: () => getPlanSummary(planIdNumber),
    enabled: validPlanId,
  });

  const restoreMutation = useMutation({
    mutationFn: ({ versionId }: { versionId: number }) => restorePlanVersion(planIdNumber, versionId),
    onSuccess: async () => {
      message.success("版本恢复成功");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["plan-versions", planIdNumber] }),
        queryClient.invalidateQueries({ queryKey: ["plan-summary", planIdNumber] }),
        queryClient.invalidateQueries({ queryKey: ["plan", planIdNumber] }),
      ]);
    },
    onError: (err: Error) => {
      message.error(err.message || "版本恢复失败");
    },
  });

  const uiVersions = useMemo<UiVersion[]>(() => {
    const list = versionsQuery.data ?? [];
    return list.map((item) => ({
      id: item.id,
      version: `v${item.version_no}`,
      source: mapSourceTypeToChinese(item.source_type),
      createdAtText: formatDateTime(item.created_at),
      summary: item.change_summary || "无变更摘要",
      raw: item,
    }));
  }, [versionsQuery.data]);

  useEffect(() => {
    if (!uiVersions.length) {
      setActiveVersionId(null);
      return;
    }
    const exists = uiVersions.some((item) => item.id === activeVersionId);
    if (!exists) {
      setActiveVersionId(uiVersions[uiVersions.length - 1].id);
    }
  }, [uiVersions, activeVersionId]);

  const activeVersion = useMemo(() => uiVersions.find((item) => item.id === activeVersionId) ?? null, [uiVersions, activeVersionId]);
  const legacyDetailsMap = useMemo<Record<string, LegacyMock>>(() => Object.fromEntries(mockVersionHistory.map((item) => [item.version, item])), []);
  const legacyDetails = activeVersion ? legacyDetailsMap[activeVersion.version] : undefined;

  const headerTitle = summaryQuery.data?.title ?? "方案版本控制";
  const headerSubtitle = summaryQuery.data ? `${summaryQuery.data.city} - 版本演进历史` : "版本演进历史";

  if (!validPlanId) {
    return (
      <Alert
        type="warning"
        showIcon
        message="缺少方案 ID 参数"
        description="请从方案历史页点击“查看版本”进入，或在 URL 中附加 ?planId=数字。"
      />
    );
  }

  if (versionsQuery.isLoading || summaryQuery.isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
        <Spin />
      </div>
    );
  }

  if (versionsQuery.isError) {
    return <Alert type="error" showIcon message="版本列表加载失败" description={versionsQuery.error.message} />;
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", paddingBottom: 40 }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          <Space>
            <GitMerge size={28} color="#722ed1" />
            方案版本控制
          </Space>
        </Title>
        <Text type="secondary">
          {headerTitle} - {headerSubtitle}
        </Text>
      </div>

      {uiVersions.length === 0 ? (
        <Card bordered={false} style={{ borderRadius: 16 }}>
          <Empty description="暂无版本记录" />
        </Card>
      ) : (
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <Card bordered={false} style={{ borderRadius: 16, height: "100%" }}>
              <Timeline
                items={uiVersions.map((ver) => ({
                  color: ver.id === activeVersionId ? "#722ed1" : "gray",
                  dot: <GitCommit size={16} color={ver.id === activeVersionId ? "#722ed1" : "#bfbfbf"} />,
                  children: (
                    <div
                      style={{
                        cursor: "pointer",
                        padding: 12,
                        borderRadius: 8,
                        background: ver.id === activeVersionId ? "#f9f0ff" : "transparent",
                        transition: "all 0.3s",
                      }}
                      onClick={() => setActiveVersionId(ver.id)}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <Text strong style={{ color: ver.id === activeVersionId ? "#722ed1" : "inherit" }}>
                          {ver.version}
                        </Text>
                        <Tag color={isAiSource(ver.raw.source_type) ? "cyan" : "blue"} style={{ border: 0 }}>
                          {isAiSource(ver.raw.source_type) ? <Bot size={12} style={{ marginRight: 4 }} /> : <User size={12} style={{ marginRight: 4 }} />}
                          {ver.source}
                        </Tag>
                      </div>
                      <Text style={{ display: "block", margin: "8px 0", fontSize: 13 }}>{ver.summary}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {ver.createdAtText}
                      </Text>
                    </div>
                  ),
                }))}
              />
            </Card>
          </Col>

          <Col xs={24} md={16}>
            {activeVersion == null ? null : (
              <motion.div key={activeVersion.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
                <Card bordered={false} style={{ borderRadius: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                    <Title level={3} style={{ margin: 0 }}>
                      版本详情 {activeVersion.version}
                    </Title>
                    <Button
                      type="primary"
                      style={{ background: "#722ed1", borderColor: "#722ed1" }}
                      loading={restoreMutation.isPending}
                      onClick={() => restoreMutation.mutate({ versionId: activeVersion.id })}
                    >
                      恢复此版本
                    </Button>
                  </div>

                  <Row gutter={24} style={{ marginBottom: 24 }}>
                    <Col span={8}>
                      <Card size="small" style={{ background: "#fafafa", border: "none" }}>
                        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                          预算变化
                        </Text>
                        <Space align="center">
                          <Text
                            strong
                            style={{
                              fontSize: 20,
                              color:
                                typeof legacyDetails?.budgetChange === "number"
                                  ? legacyDetails.budgetChange > 0
                                    ? "#cf1322"
                                    : legacyDetails.budgetChange < 0
                                      ? "#389e0d"
                                      : "#595959"
                                  : "#595959",
                            }}
                          >
                            {typeof legacyDetails?.budgetChange === "number" ? `${legacyDetails.budgetChange > 0 ? "+" : ""}${legacyDetails.budgetChange}` : "暂缺"}
                          </Text>
                          {typeof legacyDetails?.budgetChange === "number" && legacyDetails.budgetChange > 0 ? <TrendingUp color="#cf1322" size={16} /> : null}
                          {typeof legacyDetails?.budgetChange === "number" && legacyDetails.budgetChange < 0 ? <TrendingDown color="#389e0d" size={16} /> : null}
                        </Space>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ background: "#fafafa", border: "none" }}>
                        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                          天气风险评估
                        </Text>
                        <Tag color={getRiskTagColor(legacyDetails?.riskChange)}>
                          {mapRiskToChinese(legacyDetails?.riskChange)}
                        </Tag>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ background: "#fafafa", border: "none" }}>
                        <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                          行程强度
                        </Text>
                        <Text strong>{mapPaceToChinese(legacyDetails?.intensityChange)}</Text>
                      </Card>
                    </Col>
                  </Row>

                  <Divider orientation="left" plain>
                    变更详情（差异）
                  </Divider>

                  <Row gutter={24}>
                    <Col span={12}>
                      <Card size="small" title={<Space><Plus size={16} color="#52c41a" /> 新增节点</Space>} style={{ border: "1px solid #b7eb8f", background: "#f6ffed" }}>
                        {legacyDetails?.details.added.length ? (
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {legacyDetails.details.added.map((item, i) => <li key={i}>{item}</li>)}
                          </ul>
                        ) : (
                          <Text type="secondary">暂无新增</Text>
                        )}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card size="small" title={<Space><Minus size={16} color="#f5222d" /> 移除节点</Space>} style={{ border: "1px solid #ffa39e", background: "#fff1f0" }}>
                        {legacyDetails?.details.removed.length ? (
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {legacyDetails.details.removed.map((item, i) => <li key={i}>{item}</li>)}
                          </ul>
                        ) : (
                          <Text type="secondary">暂无移除</Text>
                        )}
                      </Card>
                    </Col>
                  </Row>

                  {legacyDetails?.details.reordered ? (
                    <div style={{ marginTop: 16, padding: 12, background: "#e6f7ff", border: "1px solid #91d5ff", borderRadius: 8, display: "flex", alignItems: "center", gap: 8 }}>
                      <RefreshCw size={16} color="#1890ff" />
                      <Text style={{ color: "#096dd9" }}>检测到行程顺序调整（优化路线合理性）</Text>
                    </div>
                  ) : null}

                  {!legacyDetails ? (
                    <Alert
                      style={{ marginTop: 16 }}
                      type="info"
                      showIcon
                      message="当前版本缺少差异展示字段"
                      description="预算变化、风险变化、强度变化、增删节点、是否重排仍为历史 mock 字段，后端版本接口暂未提供。"
                    />
                  ) : null}
                </Card>
              </motion.div>
            )}
          </Col>
        </Row>
      )}
    </div>
  );
}

function mapSourceTypeToChinese(sourceType: string): string {
  if (sourceType === "created") return "AI 初始生成";
  if (sourceType === "regenerated") return "AI 重生成";
  if (sourceType === "edited") return "用户编辑";
  if (sourceType === "restored") return "版本恢复";
  return `未知来源（${sourceType || "空值"}）`;
}

function isAiSource(sourceType: string): boolean {
  return sourceType === "created" || sourceType === "regenerated";
}

function mapRiskToChinese(value?: string): string {
  const v = String(value ?? "").toLowerCase();
  if (!v) return "暂缺";
  if (v === "low" || v.includes("低")) return "低";
  if (v === "medium" || v.includes("中")) return "中";
  if (v === "high" || v.includes("高")) return "高";
  return "暂缺";
}

function getRiskTagColor(value?: string): string {
  const risk = mapRiskToChinese(value);
  if (risk === "低") return "green";
  if (risk === "中") return "orange";
  if (risk === "高") return "red";
  return "default";
}

function mapPaceToChinese(value?: string): string {
  const v = String(value ?? "").toLowerCase();
  if (!v) return "暂缺";
  if (v === "relaxed" || v.includes("轻松")) return "轻松";
  if (v === "balanced" || v.includes("适中")) return "适中";
  if (v === "intensive" || v.includes("紧凑")) return "紧凑";
  return value ?? "暂缺";
}

function formatDateTime(value: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
