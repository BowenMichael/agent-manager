import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Theme } from '../../constants/Theme';
import { sessionStore } from '../../store/sessionStore';
import { ThinkingAccordion } from '../../components/ThinkingAccordion';
import { ToolCallCard } from '../../components/ToolCallCard';
import { TokenBudgetBar } from '../../components/TokenBudgetBar';

interface TranscriptEntry {
  id: string;
  role: 'user' | 'agent' | 'system' | 'tool';
  content?: string;
  thinking?: string;
  toolName?: string;
  toolArgs?: Record<string, any>;
  toolOutput?: string;
  isError?: boolean;
}

export default function SessionDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const session = sessionStore.getSession(id || '');
  const scrollViewRef = useRef<ScrollView>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const [entries, setEntries] = useState<TranscriptEntry[]>([
    { id: '1', role: 'user', content: `Start implementation for ${session?.repo || 'agent-manager'}` },
    { id: '2', role: 'agent', thinking: 'Analyzing codebase architecture, checking test files, planning worktree steps.', content: 'Initialized worktree enclave. Inspecting target files...' },
    { id: '3', role: 'tool', toolName: 'grep_search', toolArgs: { Query: 'WebSocket', SearchPath: 'apps/mobile' }, toolOutput: 'Match found in apps/mobile/services/socket.ts' },
    { id: '4', role: 'agent', thinking: 'Component built successfully. Executing test suites.', content: 'Running test verification with log suppression.' },
  ]);

  useEffect(() => {
    if (autoScroll && scrollViewRef.current) {
      scrollViewRef.current.scrollToEnd({ animated: true });
    }
  }, [entries, autoScroll]);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {session?.repo ? `${session.repo} #${session.issue_number || ''}` : `Session ${id?.substring(0, 8)}`}
        </Text>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{(session?.status || 'RUNNING').toUpperCase()}</Text>
        </View>
      </View>

      <TokenBudgetBar
        totalTokens={session?.total_tokens || 34200}
        maxTokens={150000}
        costUsd={session?.total_cost_usd || 0.042}
      />

      <ScrollView
        ref={scrollViewRef}
        style={styles.feed}
        contentContainerStyle={styles.feedContent}
        onScrollBeginDrag={() => setAutoScroll(false)}
      >
        {entries.map((entry) => (
          <View key={entry.id} style={styles.entryContainer}>
            {entry.thinking && (
              <ThinkingAccordion thinkingText={entry.thinking} tokenCount={120} />
            )}

            {entry.role === 'tool' && entry.toolName && (
              <ToolCallCard
                toolName={entry.toolName}
                args={entry.toolArgs}
                output={entry.toolOutput}
                isError={entry.isError}
              />
            )}

            {entry.content && (
              <View style={[styles.bubble, entry.role === 'user' ? styles.userBubble : styles.agentBubble]}>
                <Text style={styles.roleLabel}>{entry.role.toUpperCase()}</Text>
                <Text style={styles.messageText}>{entry.content}</Text>
              </View>
            )}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#21262d',
  },
  backButton: { paddingRight: 8 },
  backText: { color: Theme.primary, fontSize: 16, fontWeight: '600' },
  headerTitle: { fontSize: 14, fontWeight: 'bold', color: Theme.textPrimary, flex: 1, marginHorizontal: 8 },
  badge: { backgroundColor: 'rgba(56, 189, 248, 0.15)', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  badgeText: { color: Theme.primary, fontSize: 11, fontWeight: '700' },
  feed: { flex: 1 },
  feedContent: { padding: 16, gap: 8 },
  entryContainer: { marginVertical: 4 },
  bubble: { padding: 12, borderRadius: 8, marginVertical: 2 },
  userBubble: { backgroundColor: '#1e293b', alignSelf: 'flex-end', maxWidth: '85%' },
  agentBubble: { backgroundColor: '#161b22', alignSelf: 'flex-start', maxWidth: '95%' },
  roleLabel: { fontSize: 10, fontWeight: '700', color: Theme.textMuted, marginBottom: 4 },
  messageText: { fontSize: 13, color: Theme.textPrimary, lineHeight: 18 },
});
