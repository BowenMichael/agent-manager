import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  SafeAreaView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Theme } from '../constants/Theme';
import { sessionStore, MobileAgentSession, StatusFilter } from '../store/sessionStore';
import { agentSocket, ConnectionStatus } from '../services/socket';

export default function SessionsFeedScreen() {
  const router = useRouter();
  const [sessions, setSessions] = useState<MobileAgentSession[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    agentSocket.connect();
    sessionStore.fetchSessions();

    const unsubscribe = sessionStore.subscribe(() => {
      setSessions(sessionStore.getSessions());
      setStatus(sessionStore.getConnectionStatus());
      setFilter(sessionStore.getFilter());
    });

    return () => unsubscribe();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await sessionStore.fetchSessions();
    setRefreshing(false);
  };

  const renderFilterButton = (key: StatusFilter, label: string) => (
    <TouchableOpacity
      key={key}
      style={[styles.filterBtn, filter === key && styles.filterBtnActive]}
      onPress={() => sessionStore.setFilter(key)}
    >
      <Text style={[styles.filterText, filter === key && styles.filterTextActive]}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      {status !== 'connected' && (
        <View style={[styles.banner, status === 'reconnecting' ? styles.bannerWarn : styles.bannerError]}>
          <Text style={styles.bannerText}>
            {status === 'reconnecting' ? '⚡ Reconnecting to Agent Manager...' : '⚠️ Offline / Disconnected'}
          </Text>
        </View>
      )}

      <View style={styles.filterRow}>
        {renderFilterButton('all', 'All')}
        {renderFilterButton('active', 'Active')}
        {renderFilterButton('in_review', 'In Review')}
        {renderFilterButton('completed', 'Done')}
        {renderFilterButton('failed', 'Failed')}
      </View>

      <FlatList
        data={sessions}
        keyExtractor={(item) => item.session_id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Theme.primary} />}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => router.push(`/session/${item.session_id}`)}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.repoText}>{item.repo}</Text>
              <View style={[styles.badge, getBadgeStyle(item.status)]}>
                <Text style={[styles.badgeText, { color: getBadgeTextColor(item.status) }]}>
                  {item.status.toUpperCase()}
                </Text>
              </View>
            </View>

            <Text style={styles.activityText} numberOfLines={2}>
              {item.current_activity || `Session ${item.session_id.substring(0, 8)}`}
            </Text>

            <View style={styles.cardFooter}>
              <Text style={styles.metaText}>
                {item.issue_number ? `Issue #${item.issue_number}` : 'Autonomous Flywheel'}
              </Text>
              {item.total_cost_usd !== undefined && (
                <Text style={styles.costText}>${item.total_cost_usd.toFixed(4)}</Text>
              )}
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No sessions found matching filter</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

function getBadgeStyle(status: string) {
  switch (status) {
    case 'running': return { backgroundColor: 'rgba(56, 189, 248, 0.15)' };
    case 'in_review': return { backgroundColor: 'rgba(245, 158, 11, 0.15)' };
    case 'completed': return { backgroundColor: 'rgba(34, 197, 94, 0.15)' };
    case 'paused': return { backgroundColor: 'rgba(234, 179, 8, 0.15)' };
    default: return { backgroundColor: 'rgba(239, 68, 68, 0.15)' };
  }
}

function getBadgeTextColor(status: string) {
  switch (status) {
    case 'running': return Theme.primary;
    case 'in_review': return Theme.warning;
    case 'completed': return Theme.success;
    case 'paused': return '#eab308';
    default: return Theme.error;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.background },
  banner: { paddingVertical: 8, paddingHorizontal: 16, alignItems: 'center' },
  bannerWarn: { backgroundColor: 'rgba(245, 158, 11, 0.2)' },
  bannerError: { backgroundColor: 'rgba(239, 68, 68, 0.2)' },
  bannerText: { fontSize: 12, fontWeight: '600', color: Theme.textMuted },
  filterRow: { flexDirection: 'row', padding: 12, gap: 8 },
  filterBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, backgroundColor: Theme.cardBg },
  filterBtnActive: { backgroundColor: Theme.primary },
  filterText: { fontSize: 13, color: Theme.textMuted },
  filterTextActive: { color: '#000', fontWeight: 'bold' },
  card: { backgroundColor: Theme.cardBg, marginHorizontal: 16, marginVertical: 6, padding: 16, borderRadius: 12 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  repoText: { fontSize: 14, fontWeight: 'bold', color: Theme.textPrimary },
  badge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  activityText: { fontSize: 13, color: Theme.textMuted, marginBottom: 12 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  metaText: { fontSize: 12, color: Theme.textMuted },
  costText: { fontSize: 12, fontWeight: '600', color: Theme.success },
  emptyContainer: { padding: 40, alignItems: 'center' },
  emptyText: { color: Theme.textMuted, fontSize: 14 },
});
