import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { AuthorizedVehiclesPage } from './pages/AuthorizedVehiclesPage';
import { SpottedVehiclesPage } from './pages/SpottedVehiclesPage';
import { ViolationsPage } from './pages/ViolationsPage';
import { LiveCameraPage } from './pages/LiveCameraPage';
import { Navbar } from './components/Navbar';
import { WhatsAppSettingsModal } from './components/WhatsAppSettingsModal';
import {
  SystemStats,
  fetchSystemStats,
  fetchWhatsAppConfig,
  fetchWhatsAppGatewayStatus,
} from './api/client';

const Dashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'authorized' | 'spotted' | 'violations' | 'live-camera'>('authorized');
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isWhatsAppModalOpen, setIsWhatsAppModalOpen] = useState(false);
  const [isWhatsAppConfigured, setIsWhatsAppConfigured] = useState(false);

  const loadStats = async () => {
    try {
      setIsRefreshing(true);
      const data = await fetchSystemStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load system stats', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const loadWhatsAppStatus = async () => {
    try {
      const [gw, cfg] = await Promise.all([
        fetchWhatsAppGatewayStatus().catch(() => null),
        fetchWhatsAppConfig().catch(() => null),
      ]);
      setIsWhatsAppConfigured(Boolean(gw?.connected || cfg?.configured));
    } catch (err) {
      console.error('Failed to load WhatsApp status', err);
    }
  };

  useEffect(() => {
    loadStats();
    loadWhatsAppStatus();
    const interval = setInterval(() => {
      loadStats();
      loadWhatsAppStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'live-camera') {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [activeTab]);

  return (
    <div
      className={`bg-slate-950 text-slate-100 flex flex-col w-full max-w-full overflow-x-hidden ${
        activeTab === 'live-camera' ? 'h-screen max-h-screen overflow-hidden' : 'min-h-screen'
      }`}
    >
      {/* Aesthetic Top Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        onRefresh={loadStats}
        isRefreshing={isRefreshing}
        onOpenWhatsAppSettings={() => setIsWhatsAppModalOpen(true)}
        isWhatsAppConfigured={isWhatsAppConfigured}
      />

      {/* Main Dashboard Workspace */}
      <main
        className={`w-full max-w-full min-w-0 ${
          activeTab === 'live-camera'
            ? 'flex-1 overflow-hidden flex flex-col'
            : 'flex-1 max-w-7xl mx-auto pb-12'
        }`}
      >
        {activeTab === 'authorized' ? (
          <AuthorizedVehiclesPage />
        ) : activeTab === 'spotted' ? (
          <SpottedVehiclesPage />
        ) : activeTab === 'violations' ? (
          <ViolationsPage onOpenWhatsAppSettings={() => setIsWhatsAppModalOpen(true)} />
        ) : (
          <LiveCameraPage />
        )}
      </main>

      {/* Meta WhatsApp Business Cloud API Settings Modal */}
      <WhatsAppSettingsModal
        isOpen={isWhatsAppModalOpen}
        onClose={() => setIsWhatsAppModalOpen(false)}
        onConfigSaved={loadWhatsAppStatus}
      />
    </div>
  );
};

const MainApp: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-xs text-slate-400 font-mono">Initializing Just Meter Portal...</p>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <Dashboard /> : <LoginPage />;
};

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
