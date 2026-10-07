/**
 * Token Budget Progress Bar Component.
 * Displays total token usage vs session budget quota with warning thresholds.
 * Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Theme } from '../constants/Theme';

interface TokenBudgetBarProps {
  totalTokens: number;
  maxTokens?: number;
  costUsd?: number;
}

export const TokenBudgetBar: React.FC<TokenBudgetBarProps> = ({
  totalTokens,
  maxTokens = 150000,
  costUsd,
}) => {
  const percent = Math.min(Math.round((totalTokens / maxTokens) * 100), 100);
  const barColor = getProgressColor(percent);

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={styles.label}>
          Token Budget: <Text style={styles.bold}>{totalTokens.toLocaleString()}</Text> / {maxTokens.toLocaleString()} ({percent}%)
        </Text>
        {costUsd !== undefined && (
          <Text style={styles.costLabel}>${costUsd.toFixed(4)}</Text>
        )}
      </View>

      <View style={styles.track}>
        <View style={[styles.fill, { width: `${percent}%`, backgroundColor: barColor }]} />
      </View>
    </View>
  );
};

function getProgressColor(percent: number): string {
  if (percent >= 90) return Theme.error;
  if (percent >= 70) return Theme.warning;
  return Theme.primary;
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: Theme.cardBg,
    borderRadius: 8,
    marginHorizontal: 16,
    marginVertical: 6,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  label: {
    fontSize: 12,
    color: Theme.textMuted,
  },
  bold: {
    fontWeight: 'bold',
    color: Theme.textPrimary,
  },
  costLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: Theme.success,
  },
  track: {
    height: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 3,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: 3,
  },
});
