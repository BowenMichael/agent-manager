/**
 * Collapsible Thinking & Internal Reasoning Component.
 * Displays agent cognitive traces with token counts and accordion toggle.
 * Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Theme } from '../constants/Theme';

interface ThinkingAccordionProps {
  thinkingText: string;
  tokenCount?: number;
  initiallyExpanded?: boolean;
}

export const ThinkingAccordion: React.FC<ThinkingAccordionProps> = ({
  thinkingText,
  tokenCount,
  initiallyExpanded = false,
}) => {
  const [expanded, setExpanded] = useState(initiallyExpanded);

  if (!thinkingText.trim()) return null;

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.header}
        onPress={() => setExpanded(!expanded)}
        activeOpacity={0.7}
      >
        <View style={styles.headerLeft}>
          <Text style={styles.icon}>{expanded ? '▼' : '▶'}</Text>
          <Text style={styles.headerTitle}>Reasoning Trace</Text>
        </View>
        {tokenCount !== undefined && (
          <View style={styles.tokenBadge}>
            <Text style={styles.tokenText}>{tokenCount} tokens</Text>
          </View>
        )}
      </TouchableOpacity>

      {expanded && (
        <View style={styles.content}>
          <Text style={styles.thinkingText}>{thinkingText}</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: Theme.primary,
    marginVertical: 4,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  icon: {
    fontSize: 10,
    color: Theme.primary,
  },
  headerTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: Theme.textMuted,
  },
  tokenBadge: {
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  tokenText: {
    fontSize: 10,
    color: Theme.primary,
    fontWeight: '600',
  },
  content: {
    paddingHorizontal: 12,
    paddingBottom: 10,
  },
  thinkingText: {
    fontSize: 12,
    fontFamily: 'monospace',
    color: Theme.textMuted,
    lineHeight: 18,
  },
});
