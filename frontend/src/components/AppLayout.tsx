import type { PropsWithChildren } from "react";
import { Layout, Menu, Space, Typography, Button, Avatar, Dropdown, theme } from "antd";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Compass, User, LayoutDashboard, History, LogOut, Map } from "lucide-react";

import { useAuthStore } from "../store/auth";

const { Header, Content, Sider } = Layout;

export function AppLayout({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);

  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  const userMenu = {
    items: [
      {
        key: '1',
        icon: <User size={16} />,
        label: '个人设置',
        onClick: () => navigate("/profile"),
      },
      {
        key: '2',
        icon: <LogOut size={16} />,
        label: '退出登录',
        onClick: handleLogout,
      },
    ],
  };

  return (
    <Layout style={{ minHeight: "100vh", backgroundColor: "#f0f2f5" }}>
      <Sider 
        width={260} 
        theme="dark" 
        style={{ 
          background: "#001529", 
          boxShadow: "2px 0 8px rgba(0,0,0,0.15)", 
          zIndex: 10,
        }}
      >
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 16px', color: '#fff' }}>
          <Space>
            <Compass size={28} color="#13c2c2" />
            <Typography.Title level={4} style={{ color: "#fff", margin: 0, letterSpacing: '1px' }}>
              TravelOS
            </Typography.Title>
          </Space>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          style={{ background: "transparent", borderRight: 0, padding: '16px 8px' }}
          items={[
            { 
              key: "/", 
              icon: <LayoutDashboard size={18} />, 
              label: <Link to="/">工作台首页</Link> 
            },
            { 
              key: "/history", 
              icon: <History size={18} />, 
              label: <Link to="/history">方案档案馆</Link> 
            },
            { 
              key: "/profile", 
              icon: <User size={18} />, 
              label: <Link to="/profile">旅行画像</Link> 
            },
          ]}
        />
        
        {/* Mock Map / Activity Background at bottom of Sider */}
        <div style={{ position: 'absolute', bottom: 20, width: '100%', padding: '0 24px', opacity: 0.5 }}>
           <div style={{ 
             height: 120, 
             background: 'linear-gradient(180deg, transparent 0%, rgba(19, 194, 194, 0.1) 100%)', 
             borderRadius: 12,
             border: '1px solid rgba(255,255,255,0.1)',
             display: 'flex',
             flexDirection: 'column',
             alignItems: 'center',
             justifyContent: 'center'
           }}>
             <Map size={32} color="#13c2c2" />
             <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>AI 路线引擎就绪</div>
           </div>
        </div>
      </Sider>

      <Layout>
        <Header style={{ 
            padding: "0 24px", 
            background: "#fff", 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "flex-end",
            boxShadow: "0 1px 4px rgba(0,21,41,0.08)",
            zIndex: 9
          }}>
          <Space size="middle">
            <Typography.Text style={{ color: "#666" }}>
              欢迎回来，{user?.username ?? "旅行规划师"}
            </Typography.Text>
            <Dropdown menu={userMenu} placement="bottomRight">
              <Avatar style={{ backgroundColor: '#13c2c2', cursor: 'pointer' }} icon={<User size={16} />} />
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ 
          margin: "24px", 
          padding: 0, 
          minHeight: 280, 
          position: "relative" 
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
