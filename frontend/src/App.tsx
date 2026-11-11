import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { can } from './context/permissions';
import { LoginPage } from './pages/LoginPage';
import { AuthorizedVehiclesPage } from './pages/AuthorizedVehiclesPage';
import { SpottedVehiclesPage } from './pages/SpottedVehiclesPage';
import { ViolationsPage } from './pages/ViolationsPage';
import { LiveCameraPage } from './pages/LiveCameraPage';
import { ANPRReviewPage } from './pages/ANPRReviewPage';
import { EvidencePage } from './pages/EvidencePage';
import { GeofencesPage } from './pages/GeofencesPage';
import { ExecutiveDashboardPage } from './pages/ExecutiveDashboardPage';
import { VimsPage } from './pages/VimsPage';
import { VehicleProfilePage } from './pages/VehicleProfilePage';
import { ChallansPage, ChallanSelection } from './pages/ChallansPage';
import { UsersPage, ReportsPage, AuditPage } from './pages/GovernancePages';
import { TwinReference } from './api/client';
import { Navbar, AppTab } from './components/Navbar';
import { WhatsAppSettingsModal } from './components/WhatsAppSettingsModal';
import {
  SystemStats,
  fetchSystemStats,
  fetchWhatsAppConfig,
  fetchWhatsAppGatewayStatus,
} from './api/client';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const canManageSettings = can(user?.role, 'manage_settings');
  const [activeTab, setActiveTab] = useState<AppTab>(user?.role === 'Auditor' ? 'reports' : 'dashboard');
  const [vehicleReference, setVehicleReference] = useState<TwinReference | null>(null);
  const [challanSelection, setChallanSelection] = useState<ChallanSelection | null>(null);
  useEffect(() => {
    const openChallan = (event: Event) => {
      if (user?.role === 'Auditor') return;
      setChallanSelection((event as CustomEvent<ChallanSelection>).detail);
      setActiveTab('challans');
    };
    window.addEventListener('justmeter:challan', openChallan);
    return () => window.removeEventListener('justmeter:challan', openChallan);
  }, []);
  useEffect(() => {
    const openProfile = (event: Event) => {
      if (user?.role === 'Auditor') return;
      setVehicleReference((event as CustomEvent<TwinReference>).detail);
      setActiveTab('digital-twin');
    };
    window.addEventListener('justmeter:vehicle-profile', openProfile);
    return () => window.removeEventListener('justmeter:vehicle-profile', openProfile);
  }, []);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isWhatsAppModalOpen, setIsWhatsAppModalOpen] = useState(false);
  const [isWhatsAppConfigured, setIsWhatsAppConfigured] = useState(false);
  const [forbiddenMessage, setForbiddenMessage] = useState('');

  useEffect(() => {
    const handleForbidden = (event: Event) => {
      setForbiddenMessage((event as CustomEvent<string>).detail || 'Your role does not allow this action.');
    };
    window.addEventListener('justmeter:forbidden', handleForbidden);
    return () => window.removeEventListener('justmeter:forbidden', handleForbidden);
  }, []);

  const loadStats = async () => {
    if (user?.role === 'Auditor') return;
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
    if (!canManageSettings) return;
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
    const previousOverflow = document.body.style.overflow;
    const updateScrollMode = () => {
      const desktopLiveCamera = activeTab === 'live-camera'
        && window.matchMedia('(min-width: 1024px)').matches;
      document.body.style.overflow = desktopLiveCamera ? 'hidden' : '';
    };
    updateScrollMode();
    window.addEventListener('resize', updateScrollMode);
    return () => {
      window.removeEventListener('resize', updateScrollMode);
      document.body.style.overflow = previousOverflow;
    };
  }, [activeTab]);

  return (
    <div
      className={`bg-slate-950 text-slate-100 flex flex-col w-full max-w-full overflow-x-hidden ${
        activeTab === 'live-camera'
          ? 'min-h-screen lg:h-screen lg:max-h-screen lg:overflow-hidden'
          : 'min-h-screen'
      }`}
    >
      {/* Aesthetic Top Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        onRefresh={loadStats}
        isRefreshing={isRefreshing}
        onOpenWhatsAppSettings={canManageSettings ? () => setIsWhatsAppModalOpen(true) : undefined}
        isWhatsAppConfigured={isWhatsAppConfigured}
      />

      {forbiddenMessage && (
        <div role="alert" className="mx-auto mt-3 w-full max-w-7xl px-4">
          <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-700/60 bg-amber-950/50 px-3 py-2 text-sm text-amber-200">
            <span>{forbiddenMessage}</span>
            <button onClick={() => setForbiddenMessage('')} className="text-xs underline">Dismiss</button>
          </div>
        </div>
      )}

      {user && ['Transport Officer', 'Supervisory Officer'].includes(user.role) && !user.department_id && (
        <p role="status" className="px-5 py-3 text-amber-200">Your account needs a department assignment. Ask an administrator to assign one in User access.</p>
      )}

      {/* Main Dashboard Workspace */}
      <main
        className={`w-full max-w-full min-w-0 ${
          activeTab === 'live-camera'
            ? 'flex-1 min-h-0 flex flex-col lg:overflow-hidden'
            : 'flex-1 max-w-7xl mx-auto pb-12'
        }`}
      >
        {activeTab === 'users' && user?.role === 'Administrator' ? (
          <UsersPage />
        ) : activeTab === 'reports' ? (
          <ReportsPage />
        ) : activeTab === 'audit' ? (
          <AuditPage />
        ) : activeTab === 'dashboard' ? (
          <ExecutiveDashboardPage onNavigate={setActiveTab} />
        ) : activeTab === 'challans' ? (
          <ChallansPage selection={challanSelection} />
        ) : activeTab === 'digital-twin' ? (
          <VehicleProfilePage reference={vehicleReference} />
        ) : activeTab === 'vims' ? (
          <VimsPage />
        ) : activeTab === 'authorized' ? (
          <AuthorizedVehiclesPage />
        ) : activeTab === 'spotted' ? (
          <SpottedVehiclesPage />
        ) : activeTab === 'anpr-review' ? (
          <ANPRReviewPage />
        ) : activeTab === 'evidence' ? (
          <EvidencePage />
        ) : activeTab === 'geofences' ? (
          <GeofencesPage />
        ) : activeTab === 'violations' ? (
          <ViolationsPage onOpenWhatsAppSettings={canManageSettings ? () => setIsWhatsAppModalOpen(true) : undefined} />
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
