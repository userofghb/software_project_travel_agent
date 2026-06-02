import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Empty, Space, Spin, Tag } from "antd";
import { MapPin } from "lucide-react";

declare global {
  interface Window {
    AMap?: AMapNamespace;
    _AMapSecurityConfig?: {
      securityJsCode?: string;
    };
  }
}

type AMapNamespace = {
  Map: new (container: HTMLDivElement, options: Record<string, unknown>) => AMapInstance;
  Marker: new (options: Record<string, unknown>) => AMapOverlay;
  Pixel: new (x: number, y: number) => unknown;
  InfoWindow: new (options: Record<string, unknown>) => {
    open: (map: AMapInstance, position: [number, number]) => void;
  };
};

type AMapInstance = {
  add: (overlay: AMapOverlay | AMapOverlay[]) => void;
  remove: (overlay: AMapOverlay | AMapOverlay[]) => void;
  resize?: () => void;
  setFitView: (overlays?: AMapOverlay[], immediately?: boolean, avoid?: number[]) => void;
  destroy: () => void;
};

type AMapOverlay = {
  on?: (eventName: string, handler: () => void) => void;
};

export type MapPoint = {
  id?: string | number | null;
  node_id?: string | number | null;
  name?: string | null;
  type?: string | null;
  address?: string | null;
  day?: string | number | null;
  order?: string | number | null;
  location?: {
    lng?: number | string | null;
    lat?: number | string | null;
  } | null;
};

export type MapRoute = {
  day?: string | number | null;
  from?: string | null;
  to?: string | null;
  mode?: string | null;
  distance_m?: number | null;
  duration_s?: number | null;
  polyline?: string | null;
  source?: string | null;
};

type PlanMapProps = {
  points?: MapPoint[];
  routes?: MapRoute[];
  activeDate?: string;
  selectedNodeId?: string | null;
  onPointSelect?: (nodeId: string) => void;
  height?: number;
};

const AMAP_KEY = import.meta.env.VITE_AMAP_JS_API_KEY as string | undefined;
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_JS_CODE as string | undefined;
let amapLoader: Promise<AMapNamespace> | null = null;

function loadAmap(): Promise<AMapNamespace> {
  if (window.AMap) {
    return Promise.resolve(window.AMap);
  }
  if (!AMAP_KEY) {
    return Promise.reject(new Error("VITE_AMAP_JS_API_KEY is not configured"));
  }
  if (AMAP_SECURITY_CODE) {
    window._AMapSecurityConfig = { securityJsCode: AMAP_SECURITY_CODE };
  }
  if (!amapLoader) {
    amapLoader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.id = "amap-js-api";
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(AMAP_KEY)}`;
      script.async = true;
      script.onload = () => {
        if (window.AMap) {
          resolve(window.AMap);
        } else {
          reject(new Error("高德地图脚本已加载，但未发现 AMap 全局对象"));
        }
      };
      script.onerror = () => reject(new Error("高德地图 JS API 加载失败"));
      document.head.appendChild(script);
    });
  }
  return amapLoader;
}

function toLngLat(point: MapPoint): [number, number] | null {
  const lng = Number(point.location?.lng);
  const lat = Number(point.location?.lat);
  return Number.isFinite(lng) && Number.isFinite(lat) ? [lng, lat] : null;
}

function pointTypeLabel(type?: string | null) {
  if (type === "hotel") return "酒店";
  if (type === "food") return "餐馆";
  if (type === "transport_hub") return "车站/机场";
  if (type === "attraction") return "景点";
  return "地点";
}

function pointNodeId(point: MapPoint): string {
  return String(point.node_id ?? point.id ?? "");
}

function markerContent(point: MapPoint, selected: boolean) {
  const type = point.type;
  const color = type === "hotel" ? "#722ed1" : type === "food" ? "#fa8c16" : type === "transport_hub" ? "#13c2c2" : "#1677ff";
  const label = type === "hotel" ? "住" : type === "food" ? "食" : type === "transport_hub" ? "站" : String(point.order ?? "游");
  const size = selected ? 36 : 30;
  return `<div style="display:flex;align-items:center;gap:6px;transform:translateY(-2px);">
    <div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};color:white;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;box-shadow:0 4px 12px rgba(0,0,0,.22);border:${selected ? 3 : 2}px solid ${selected ? "#faad14" : "white"};">${label}</div>
    <div style="max-width:120px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;background:white;color:#172033;border:1px solid rgba(0,0,0,.08);border-radius:6px;padding:2px 6px;font-size:12px;box-shadow:0 3px 10px rgba(0,0,0,.12);">${point.name ?? "地点"}</div>
  </div>`;
}

export function PlanMap({ points = [], activeDate, selectedNodeId, onPointSelect, height = 320 }: PlanMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMapInstance | null>(null);
  const overlaysRef = useRef<AMapOverlay[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");

  const visiblePoints = useMemo(
    () =>
      points.filter((point) => {
        if (!activeDate || point.type === "hotel" || !point.day) {
          return true;
        }
        return String(point.day) === activeDate;
      }),
    [points, activeDate],
  );
  const validPoints = useMemo(() => visiblePoints.filter((point) => toLngLat(point)), [visiblePoints]);
  const pointCounts = useMemo(
    () => ({
      attraction: validPoints.filter((point) => point.type === "attraction").length,
      food: validPoints.filter((point) => point.type === "food").length,
      hotel: validPoints.filter((point) => point.type === "hotel").length,
    }),
    [validPoints],
  );

  useEffect(() => {
    if (!containerRef.current || !AMAP_KEY || validPoints.length === 0) {
      return;
    }
    let disposed = false;
    setStatus("loading");
    loadAmap()
      .then((AMap) => {
        if (disposed || !containerRef.current) {
          return;
        }
        const firstPoint = toLngLat(validPoints[0])!;
        mapRef.current = new AMap.Map(containerRef.current, {
          zoom: 12,
          center: firstPoint,
          viewMode: "2D",
          resizeEnable: true,
        });
        mapRef.current.resize?.();
        setStatus("ready");
      })
      .catch((exc: Error) => {
        setError(exc.message);
        setStatus("error");
      });
    return () => {
      disposed = true;
      overlaysRef.current = [];
      mapRef.current?.destroy();
      mapRef.current = null;
    };
  }, [validPoints]);

  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(() => {
      mapRef.current?.resize?.();
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const AMap = window.AMap;
    if (!map || !AMap) {
      return;
    }
    if (overlaysRef.current.length > 0) {
      map.remove(overlaysRef.current);
      overlaysRef.current = [];
    }

    const markers = validPoints.map((point) => {
      const position = toLngLat(point)!;
      const nodeId = pointNodeId(point);
      const selected = Boolean(selectedNodeId && nodeId === selectedNodeId);
      const marker = new AMap.Marker({
        position,
        content: markerContent(point, selected),
        offset: new AMap.Pixel(-15, -15),
        title: point.name,
      });
      marker.on?.("click", () => {
        if (nodeId) {
          onPointSelect?.(nodeId);
        }
        new AMap.InfoWindow({
          content: `<div style="min-width:180px"><div style="font-size:12px;color:#1677ff;margin-bottom:4px">${pointTypeLabel(point.type)}</div><strong>${point.name ?? "地点"}</strong><div style="margin-top:4px;color:#666">${point.address ?? ""}</div></div>`,
          offset: new AMap.Pixel(0, -18),
        }).open(map, position);
      });
      return marker;
    });

    overlaysRef.current = markers;
    map.add(overlaysRef.current);
    map.setFitView(overlaysRef.current, false, [44, 32, 76, 32]);
    window.setTimeout(() => map.resize?.(), 0);
  }, [validPoints, selectedNodeId, onPointSelect]);

  if (!AMAP_KEY) {
    return (
      <div style={{ height, minHeight: height, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
        <Alert
          type="warning"
          showIcon
          message="未配置高德地图前端 Key"
          description="请在 frontend/.env 中设置 VITE_AMAP_JS_API_KEY。后端路线数据仍由 AMAP_API_KEY 控制。"
        />
      </div>
    );
  }

  if (validPoints.length === 0) {
    return (
      <div style={{ height, minHeight: height, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可展示的经纬度数据" />
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height, minHeight: height, overflow: "hidden", borderRadius: 8 }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: height }} />
      {status === "loading" && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(255,255,255,.7)" }}>
          <Spin />
        </div>
      )}
      {status === "error" && (
        <div style={{ position: "absolute", inset: 12 }}>
          <Alert type="error" showIcon message="高德地图加载失败" description={error} />
        </div>
      )}
      <Space size={8} style={{ position: "absolute", left: 12, top: 12, flexWrap: "wrap" }}>
        <Tag icon={<MapPin size={12} />} color="blue">{validPoints.length} 个地点</Tag>
        {pointCounts.attraction > 0 && <Tag color="blue">{pointCounts.attraction} 景点</Tag>}
        {pointCounts.food > 0 && <Tag color="orange">{pointCounts.food} 餐馆</Tag>}
        {pointCounts.hotel > 0 && <Tag color="purple">{pointCounts.hotel} 酒店</Tag>}
      </Space>
    </div>
  );
}
