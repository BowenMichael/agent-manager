import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Pressable,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Theme } from '../constants/Theme';
import { Config } from '../constants/Config';

interface MockSession {
  id: string;
  issueNumber: number;
  title: string;
  status: 'running' | 'in_review' | 'completed' | 'paused';
  model: string;
  turns: number;
  updatedAt: string;
}

const MOCK_SESSIONS: MockSession[] = [
  {
    id: 'sess-issue-20',
    issueNumber: 20,
    title: '[EXPO]: Scaffold Expo Application with TypeScript and Expo Router',
    status: 'running',
    model: 'Gemini 3.8 Flash',
    turns: 4,
    updatedAt: 'Just now',
  },
  {
    id: 'sess-issue-17',
    issueNumber: 17,
    title: '[BACKEND]: Decouple Windows paths and cross-platform fallbacks',
    status: 'completed',
    model: 'Gemini 3.1 Pro',
    turns: 9,
    updatedAt: '2h ago',
  },
  {
    id: 'sess-issue-65',
    issueNumber: 65,
    title: '[TELEMETRY]: Transform modal to full telemetry dashboard',
    status: 'in_review',
    model: 'Claude 3.7 Sonnet',
    turns: 12,
    updatedAt: 'Yesterday',
  },
];

const getStatusBadgeStyle = (status: MockSession['status']) => {
  switch (status) {
    case 'running':
      return { bg: 'rgba(56, 189, 248, 0.15)', text: Theme.primary };
    case 'in_review':
      return { bg: 'rgba(245, 158, 11, 0.15)', text: Theme.warning };
    case 'completed':
      return { bg: 'rgba(16, 185, 129, 0.15)', text: Theme.success };
    case 'paused':
      return { bg: 'rgba(239, 68, 68, 0.15)', text: Theme.danger };
  }
};

export default function SessionsScreen() {
  const router = useRouter();
  const [sessions] = useState<MockSession[]>(MOCK_SESSIONS);

  const renderSessionItem = ({ item }: { item: MockSession }) => {
    const badge = getStatusBadgeStyle(item.status);
    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.7}
        onPress={() => router.push(`/session/${item.id}`)}
      >
        <View style={styles.cardHeader}>
          <Text style={styles.issueNumber}>#{item.issueNumber}</Text>
          <View style={[styles.badge, { backgroundColor: badge.bg }]}>
            <Text style={[styles.badgeText, { color: badge.text }]}>
              {item.status.toUpperCase().replace('_', ' ')}
            </Text>
          </View>
        </View>

        <Text style={styles.cardTitle} numberOfLines={2}>
          {item.title}
        </Text>

        <View style={styles.cardFooter}>
          <Text style={styles.metaText}>{item.model}</Text>
          <Text style={styles.metaSeparator}>•</Text>
          <Text style={styles.metaText}>{item.turns} turns</Text>
          <Text style={styles.metaSeparator}>•</Text>
          <Text style={styles.metaText}>{item.updatedAt}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <View>
          <Text style={styles.headerTitle}>Active Agent Sessions</Text>
          <Text style={styles.headerSubtitle}>
            Connected to {Config.apiUrl}
          </Text>
        </View>
        <Pressable
          style={styles.settingsButton}
          onPress={() => router.push('/settings')}
        >
          <Text style={styles.settingsButtonText}>Settings</Text>
        </Pressable>
      </View>

      <FlatList
        data={sessions}
        keyExtractor={(item) => item.id}
        renderItem={renderSessionItem}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Theme.background,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Theme.borderLight,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: Theme.text,
  },
  headerSubtitle: {
    fontSize: 12,
    color: Theme.textMuted,
    marginTop: 2,
  },
  settingsButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: Theme.surfaceSubtle,
    borderWidth: 1,
    borderColor: Theme.border,
  },
  settingsButtonText: {
    color: Theme.text,
    fontSize: 13,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  card: {
    backgroundColor: Theme.card,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: Theme.borderLight,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  issueNumber: {
    fontSize: 13,
    fontWeight: '700',
    color: Theme.primary,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: Theme.text,
    lineHeight: 20,
    marginBottom: 12,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  metaText: {
    fontSize: 12,
    color: Theme.textSecondary,
  },
  metaSeparator: {
    marginHorizontal: 6,
    color: Theme.textSecondary,
  },
});
