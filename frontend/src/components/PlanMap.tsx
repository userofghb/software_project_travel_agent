import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Empty, Select, Space, Spin, Tag, Typography } from "antd";
import { ExternalLink, MapPin, Route } from "lucide-react";

const { Text } = Typography;

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
  Polyline: new (options: Record<string, unknown>) => AMapOverlay;
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
  name?: string | null;
  type?: string | null;
  address?: string | null;
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

function parsePolyline(polyline?: string | null): [number, number][] {
  if (!polyline) {
    return [];
  }
  return polyline
    .split(";")
    .map((item) => item.split(",").map(Number))
    .filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat)) as [number, number][];
}

function routeLabel(route: MapRoute) {
  const distance = route.distance_m ? `${(route.distance_m / 1000).toFixed(1)} km` : "距离待估";
  const duration = route.duration_s ? `${Math.round(route.duration_s / 60)} 分钟` : "耗时待估";
  return `${distance} / ${duration}`;
}

function markerContent(type?: string | null) {
  const isHotel = type === "hotel";
  const color = isHotel ? "#fa8c16" : "#1677ff";
  const label = isHotel ? "住" : "游";
  return `<div style="width:28px;height:28px;border-radius:50%;background:${color};color:white;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;box-shadow:0 4px 12px rgba(0,0,0,.22);border:2px solid white;">${label}</div>`;
}

export function PlanMap({ points = [], routes = [], activeDate, height = 320 }: PlanMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMapInstance | null>(null);
  const overlaysRef = useRef<AMapOverlay[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState<string | undefined>(activeDate);

  const validPoints = useMemo(() => points.filter((point) => toLngLat(point)), [points]);
  const routeDates = useMemo(
    () => Array.from(new Set(routes.map((route) => String(route.day ?? "")).filter(Boolean))),
    [routes],
  );
  const currentDate = selectedDate || activeDate || routeDates[0];
  const visibleRoutes = useMemo(
    () => routes.filter((route) => !currentDate || String(route.day ?? "") === currentDate),
    [routes, currentDate],
  );

  useEffect(() => {
    setSelectedDate(activeDate);
  }, [activeDate]);

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
      const marker = new AMap.Marker({
        position,
        content: markerContent(point.type),
        offset: new AMap.Pixel(-14, -14),
        title: point.name,
      });
      marker.on?.("click", () => {
        new AMap.InfoWindow({
          content: `<div style="min-width:160px"><strong>${point.name ?? "地点"}</strong><div style="margin-top:4px;color:#666">${point.address ?? ""}</div></div>`,
          offset: new AMap.Pixel(0, -18),
        }).open(map, position);
      });
      return marker;
    });

    const lines = visibleRoutes
      .map((route) => parsePolyline(route.polyline))
      .filter((path) => path.length >= 2)
      .map(
        (path) =>
          new AMap.Polyline({
            path,
            strokeColor: "#13c2c2",
            strokeWeight: 5,
            strokeOpacity: 0.85,
            lineJoin: "round",
            lineCap: "round",
          }),
      );

    overlaysRef.current = [...markers, ...lines];
    map.add(overlaysRef.current);
    map.setFitView(overlaysRef.current, false, [44, 32, 76, 32]);
    window.setTimeout(() => map.resize?.(), 0);
  }, [validPoints, visibleRoutes]);

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
        {routeDates.length > 1 && (
          <Select
            size="small"
            value={currentDate}
            style={{ width: 150 }}
            onChange={setSelectedDate}
            options={routeDates.map((date) => ({ value: date, label: date }))}
          />
        )}
        <Tag icon={<MapPin size={12} />} color="blue">{validPoints.length} 个地点</Tag>
        <Tag icon={<Route size={12} />} color="cyan">{visibleRoutes.length} 段路线</Tag>
      </Space>
      {visibleRoutes[0] && (
        <div style={{ position: "absolute", left: 12, bottom: 12, right: 12, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, background: "rgba(255,255,255,.92)", padding: "8px 10px", borderRadius: 8, boxShadow: "0 6px 18px rgba(0,0,0,.12)" }}>
          <Text ellipsis style={{ minWidth: 0 }}>
            {visibleRoutes[0].from} 到 {visibleRoutes[0].to}: {routeLabel(visibleRoutes[0])}
          </Text>
          <Button
            size="small"
            icon={<ExternalLink size={14} />}
            href={`https://uri.amap.com/marker?position=${toLngLat(validPoints[0])?.join(",")}&name=${encodeURIComponent(validPoints[0].name ?? "旅行地点")}`}
            target="_blank"
          >
            高德
          </Button>
        </div>
      )}
    </div>
  );
}
