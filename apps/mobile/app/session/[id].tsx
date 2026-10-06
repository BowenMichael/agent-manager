import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Theme } from '../../constants/Theme';

export default function SessionDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>RUNNING</Text>
        </View>
        <Text style={styles.title}>Session: {id}</Text>
        <Text style={styles.subtitle}>
          Worktree: .worktrees/issue-20 • Gemini 3.8 Flash
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Telemetry & Metrics</Text>
        <View style={styles.metricsRow}>
          <View style={styles.metricBox}>
            <Text style={styles.metricValue}>4 / 15</Text>
            <Text style={styles.metricLabel}>Turns</Text>
          </View>
          <View style={styles.metricBox}>
            <Text style={styles.metricValue}>18.4k</Text>
            <Text style={styles.metricLabel}>Tokens</Text>
          </View>
          <View style={styles.metricBox}>
            <Text style={styles.metricValue}>$0.02</Text>
            <Text style={styles.metricLabel}>Est. Cost</Text>
          </View>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Activity Trace</Text>
        <View style={styles.logCard}>
          <Text style={styles.logTimestamp}>17:36:00</Text>
          <Text style={styles.logAction}>
            [Tool Call] write_to_file: apps/mobile/constants/Theme.ts
          </Text>
        </View>
        <View style={styles.logCard}>
          <Text style={styles.logTimestamp}>17:35:54</Text>
          <Text style={styles.logAction}>
            [Tool Call] npm install: expo-router, react-native-web
          </Text>
        </View>
      </View>

      <View style={styles.actionRow}>
        <TouchableOpacity
          style={[styles.button, styles.stopButton]}
          activeOpacity={0.8}
        >
          <Text style={styles.buttonText}>Stop Agent</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, styles.backButton]}
          activeOpacity={0.8}
          onPress={() => router.back()}
        >
          <Text style={styles.backButtonText}>Back to List</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Theme.background,
  },
  content: {
    padding: 16,
    gap: 20,
  },
  header: {
    backgroundColor: Theme.card,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Theme.borderLight,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginBottom: 8,
  },
  badgeText: {
    color: Theme.primary,
    fontSize: 11,
    fontWeight: '700',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: Theme.text,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: Theme.textMuted,
  },
  section: {
    gap: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Theme.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metricsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  metricBox: {
    flex: 1,
    backgroundColor: Theme.surfaceSubtle,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: Theme.borderLight,
    alignItems: 'center',
  },
  metricValue: {
    fontSize: 16,
    fontWeight: '700',
    color: Theme.text,
  },
  metricLabel: {
    fontSize: 12,
    color: Theme.textSecondary,
    marginTop: 2,
  },
  logCard: {
    backgroundColor: Theme.surfaceSubtle,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Theme.borderLight,
    gap: 4,
  },
  logTimestamp: {
    fontSize: 11,
    color: Theme.textSecondary,
  },
  logAction: {
    fontSize: 13,
    color: Theme.text,
    fontFamily: 'monospace',
  },
  actionRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stopButton: {
    backgroundColor: Theme.danger,
  },
  buttonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  backButton: {
    backgroundColor: Theme.surfaceSubtle,
    borderWidth: 1,
    borderColor: Theme.border,
  },
  backButtonText: {
    color: Theme.text,
    fontWeight: '600',
    fontSize: 14,
  },
});
