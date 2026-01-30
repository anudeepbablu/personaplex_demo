import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Activity,
  Server,
  Cpu,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ArrowLeft,
  Wifi,
  WifiOff,
  MessageSquare,
  Phone,
  Trash2,
} from 'lucide-react';

interface HealthStatus {
  status: string;
  personaplex_configured: boolean;
  personaplex_running: boolean;
  personaplex_error: string | null;
  twilio_configured: boolean;
  mode: 'live' | 'simulation';
}

interface SimulatedSMS {
  id: string;
  to: string;
  message: string;
  timestamp: string;
  status: string;
}

interface StatusCardProps {
  title: string;
  description: string;
  isOnline: boolean | null;
  icon: React.ReactNode;
  details?: string;
}

function StatusCard({ title, description, isOnline, icon, details }: StatusCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-deep-purple/80 to-midnight/80 border border-gray-800/50 p-6"
    >
      {/* Glow effect based on status */}
      <div
        className={`absolute inset-0 opacity-10 ${
          isOnline === null
            ? 'bg-gray-500'
            : isOnline
            ? 'bg-green-500'
            : 'bg-red-500'
        }`}
      />

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-4">
          <div className="p-3 rounded-xl bg-gradient-to-br from-royal to-deep-purple">
            {icon}
          </div>
          <StatusBadge status={isOnline} />
        </div>

        <h3 className="text-xl font-semibold text-soft-cream mb-2">{title}</h3>
        <p className="text-gray-400 text-sm mb-3">{description}</p>

        {details && (
          <div className="mt-4 pt-4 border-t border-gray-700/50">
            <p className="text-xs text-gray-500 font-mono">{details}</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: boolean | null }) {
  if (status === null) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-800/80 text-gray-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span className="text-xs font-medium">Checking...</span>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
        status
          ? 'bg-green-900/50 text-green-400 border border-green-700/50'
          : 'bg-red-900/50 text-red-400 border border-red-700/50'
      }`}
    >
      {status ? (
        <CheckCircle2 className="w-4 h-4" />
      ) : (
        <XCircle className="w-4 h-4" />
      )}
      <span className="text-xs font-medium">{status ? 'Online' : 'Offline'}</span>
    </div>
  );
}

function PulsingDot({ isOnline }: { isOnline: boolean | null }) {
  const color =
    isOnline === null
      ? 'bg-gray-500'
      : isOnline
      ? 'bg-green-500'
      : 'bg-red-500';

  return (
    <span className="relative flex h-3 w-3">
      {isOnline && (
        <span
          className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`}
        />
      )}
      <span className={`relative inline-flex rounded-full h-3 w-3 ${color}`} />
    </span>
  );
}

export function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [simulatedSMS, setSimulatedSMS] = useState<SimulatedSMS[]>([]);

  const fetchSimulatedSMS = async () => {
    try {
      const response = await fetch('/reservations/notify/sms/simulated');
      if (response.ok) {
        const data = await response.json();
        setSimulatedSMS(data.messages || []);
      }
    } catch (error) {
      console.error('Failed to fetch simulated SMS:', error);
    }
  };

  const clearSimulatedSMS = async () => {
    try {
      await fetch('/reservations/notify/sms/simulated', { method: 'DELETE' });
      setSimulatedSMS([]);
    } catch (error) {
      console.error('Failed to clear simulated SMS:', error);
    }
  };

  const checkHealth = async () => {
    setIsRefreshing(true);
    try {
      const response = await fetch('/health');
      if (response.ok) {
        const data = await response.json();
        setHealth(data);
        setBackendOnline(true);
      } else {
        setBackendOnline(false);
        setHealth(null);
      }
    } catch (error) {
      setBackendOnline(false);
      setHealth(null);
    } finally {
      setIsRefreshing(false);
      setLastChecked(new Date());
    }
  };

  useEffect(() => {
    checkHealth();
    fetchSimulatedSMS();
    // Poll every 30 seconds for health, every 10 seconds for SMS
    const healthInterval = setInterval(checkHealth, 30000);
    const smsInterval = setInterval(fetchSimulatedSMS, 10000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(smsInterval);
    };
  }, []);

  const navigateHome = () => {
    window.location.hash = '';
  };

  return (
    <div className="min-h-screen bg-midnight relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-midnight via-deep-purple to-royal opacity-80" />
      <div className="absolute inset-0 noise-overlay" />

      {/* Decorative elements */}
      <div className="absolute top-20 left-1/4 w-96 h-96 bg-green-500/5 rounded-full blur-3xl" />
      <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-accent-gold/5 rounded-full blur-3xl" />

      {/* Main content */}
      <div className="relative z-10 min-h-screen">
        {/* Header */}
        <header className="border-b border-gray-800/50 bg-midnight/50 backdrop-blur-sm">
          <div className="max-w-screen-xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={navigateHome}
                  className="p-2 rounded-lg bg-deep-purple hover:bg-royal transition-colors"
                >
                  <ArrowLeft className="w-5 h-5 text-gray-400" />
                </button>
                <div className="p-2 bg-gradient-to-br from-green-600 to-emerald-700 rounded-xl">
                  <Activity className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="font-display text-2xl text-gradient">System Dashboard</h1>
                  <p className="text-sm text-gray-500">Service Health Monitor</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {lastChecked && (
                  <span className="text-xs text-gray-500">
                    Last checked: {lastChecked.toLocaleTimeString()}
                  </span>
                )}
                <button
                  onClick={checkHealth}
                  disabled={isRefreshing}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-deep-purple hover:bg-royal border border-gray-700 transition-all disabled:opacity-50"
                >
                  <RefreshCw
                    className={`w-4 h-4 text-accent-gold ${
                      isRefreshing ? 'animate-spin' : ''
                    }`}
                  />
                  <span className="text-sm text-gray-300">Refresh</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <main className="max-w-screen-xl mx-auto px-6 py-8">
          {/* Overall Status Banner */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-8 p-4 rounded-xl border ${
              backendOnline === null
                ? 'bg-gray-900/50 border-gray-700'
                : backendOnline && health?.personaplex_running
                ? 'bg-green-900/20 border-green-700/50'
                : 'bg-amber-900/20 border-amber-700/50'
            }`}
          >
            <div className="flex items-center gap-4">
              <PulsingDot isOnline={backendOnline && health?.personaplex_running} />
              <div>
                <p className="font-medium text-soft-cream">
                  {backendOnline === null
                    ? 'Checking system status...'
                    : backendOnline && health?.personaplex_running
                    ? 'All systems operational'
                    : backendOnline
                    ? `Backend online — Running in ${health?.mode?.toUpperCase() || 'SIMULATION'} mode`
                    : 'Backend unreachable'}
                </p>
                <p className="text-sm text-gray-400">
                  {backendOnline === null
                    ? 'Please wait while we check the services'
                    : backendOnline && health?.personaplex_running
                    ? 'Voice AI is connected and ready'
                    : backendOnline
                    ? 'Text-based simulation active (PersonaPlex server not running)'
                    : 'Unable to connect to backend services'}
                </p>
              </div>
            </div>
          </motion.div>

          {/* Status Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Backend Status */}
            <StatusCard
              title="Backend API"
              description="FastAPI server handling requests and WebSocket connections"
              isOnline={backendOnline}
              icon={<Server className="w-6 h-6 text-accent-gold" />}
              details={backendOnline ? 'Endpoint: /health → 200 OK' : 'Connection failed'}
            />

            {/* PersonaPlex AI Model */}
            <StatusCard
              title="PersonaPlex AI"
              description="NVIDIA voice AI model for natural conversation"
              isOnline={backendOnline ? health?.personaplex_running ?? false : null}
              icon={<Cpu className="w-6 h-6 text-accent-copper" />}
              details={
                health?.personaplex_running
                  ? 'Model running and connected'
                  : backendOnline
                  ? `Not running (${health?.personaplex_error || 'simulation mode'})`
                  : undefined
              }
            />

            {/* WebSocket Connection */}
            <StatusCard
              title="WebSocket"
              description="Real-time audio streaming connection"
              isOnline={backendOnline}
              icon={
                backendOnline ? (
                  <Wifi className="w-6 h-6 text-green-400" />
                ) : (
                  <WifiOff className="w-6 h-6 text-red-400" />
                )
              }
              details={backendOnline ? 'WS endpoint available' : 'WebSocket unavailable'}
            />
          </div>

          {/* Additional Info Section */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-8 p-6 rounded-2xl bg-gradient-to-br from-deep-purple/50 to-midnight/50 border border-gray-800/50"
          >
            <h3 className="text-lg font-semibold text-soft-cream mb-4">Configuration Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-midnight/50">
                <span className="text-gray-400">Twilio SMS</span>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    health?.twilio_configured
                      ? 'bg-green-900/50 text-green-400'
                      : 'bg-gray-800 text-gray-500'
                  }`}
                >
                  {health?.twilio_configured ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-midnight/50">
                <span className="text-gray-400">Mode</span>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    health?.personaplex_running
                      ? 'bg-green-900/50 text-green-400'
                      : 'bg-amber-900/50 text-amber-400'
                  }`}
                >
                  {health?.personaplex_running ? 'Live Voice AI' : 'Simulation Mode'}
                </span>
              </div>
            </div>
          </motion.div>

          {/* Simulated SMS Panel */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-8 p-6 rounded-2xl bg-gradient-to-br from-deep-purple/50 to-midnight/50 border border-gray-800/50"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-accent-gold" />
                <h3 className="text-lg font-semibold text-soft-cream">Simulated SMS Messages</h3>
                <span className="px-2 py-0.5 rounded-full bg-amber-900/50 text-amber-400 text-xs">
                  Demo Mode
                </span>
              </div>
              {simulatedSMS.length > 0 && (
                <button
                  onClick={clearSimulatedSMS}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-900/30 text-red-400 hover:bg-red-900/50 transition-colors text-sm"
                >
                  <Trash2 className="w-4 h-4" />
                  Clear All
                </button>
              )}
            </div>

            {simulatedSMS.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No SMS messages yet</p>
                <p className="text-sm mt-1">Messages will appear here when the AI sends confirmations</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {simulatedSMS.map((sms) => (
                  <motion.div
                    key={sms.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="p-4 rounded-xl bg-midnight/50 border border-gray-700/50"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Phone className="w-4 h-4 text-accent-copper" />
                        <span className="font-mono text-sm text-accent-gold">{sms.to}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">
                          {new Date(sms.timestamp).toLocaleTimeString()}
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 text-xs">
                          {sms.status}
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-300 leading-relaxed">{sms.message}</p>
                    <div className="mt-2 text-xs text-gray-600 font-mono">ID: {sms.id}</div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-6 flex gap-4"
          >
            <button
              onClick={navigateHome}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-accent-gold to-accent-copper text-midnight font-semibold hover:opacity-90 transition-opacity"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Console
            </button>
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-deep-purple border border-gray-700 text-gray-300 hover:bg-royal transition-colors"
            >
              View API Docs
            </a>
          </motion.div>
        </main>
      </div>
    </div>
  );
}
