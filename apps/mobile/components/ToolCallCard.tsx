/**
 * Tool Execution Card Component.
 * Displays tool invocations, collapsible JSON arguments, and execution output/diffs.
 * Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Theme } from '../constants/Theme';

interface ToolCallCardProps {
  toolName: string;
  args?: Record<string, any> | string;
  output?: string;
  isError?: boolean;
}

export const ToolCallCard: React.FC<ToolCallCardProps> = ({
  toolName,
  args,
  output,
  isError = false,
}) => {
  const [expanded, setExpanded] = useState(false);

  const formattedArgs = typeof args === 'object' ? JSON.stringify(args, null, 2) : args;

  return (
    <View style={[styles.card, isError ? styles.cardError : styles.cardSuccess]}>
      <TouchableOpacity
        style={styles.header}
        onPress={() => setExpanded(!expanded)}
        activeOpacity={0.7}
      >
        <View style={styles.headerLeft}>
          <Text style={styles.toolIcon}>🛠️</Text>
          <Text style={styles.toolName}>{toolName}</Text>
        </View>
        <Text style={styles.expandIcon}>{expanded ? '▲' : '▼'}</Text>
      </TouchableOpacity>

      {expanded && (
        <View style={styles.body}>
          {formattedArgs && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Arguments:</Text>
              <Text style={styles.codeBlock}>{formattedArgs}</Text>
            </View>
          )}

          {output && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>Output / Diff:</Text>
              <Text style={[styles.codeBlock, isError && styles.errorOutput]}>
                {output}
              </Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#161b22',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#30363d',
    marginVertical: 4,
    overflow: 'hidden',
  },
  cardSuccess: {
    borderLeftWidth: 3,
    borderLeftColor: Theme.success,
  },
  cardError: {
    borderLeftWidth: 3,
    borderLeftColor: Theme.error,
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
  toolIcon: {
    fontSize: 12,
  },
  toolName: {
    fontSize: 13,
    fontFamily: 'monospace',
    fontWeight: '600',
    color: Theme.textPrimary,
  },
  expandIcon: {
    fontSize: 10,
    color: Theme.textMuted,
  },
  body: {
    paddingHorizontal: 12,
    paddingBottom: 10,
    borderTopWidth: 1,
    borderTopColor: '#21262d',
  },
  section: {
    marginTop: 8,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: Theme.textMuted,
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  codeBlock: {
    fontSize: 11,
    fontFamily: 'monospace',
    color: '#c9d1d9',
    backgroundColor: '#0d1117',
    padding: 8,
    borderRadius: 6,
    lineHeight: 16,
  },
  errorOutput: {
    color: Theme.error,
  },
});
