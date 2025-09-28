"""
Data Sampler Component for ARGO Float Dashboard

This component provides intelligent data sampling strategies
for handling large datasets while maintaining data quality and accuracy.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, Any, Optional, List, Tuple, Callable, Union
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger(__name__)

class SamplingStrategy(Enum):
    """Available sampling strategies"""
    RANDOM = "random"
    SYSTEMATIC = "systematic"
    STRATIFIED = "stratified"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    ADAPTIVE = "adaptive"
    IMPORTANCE = "importance"

@dataclass
class SamplingConfig:
    """Configuration for data sampling"""
    strategy: SamplingStrategy
    target_size: int
    preserve_extremes: bool = True
    preserve_recent: bool = True
    quality_threshold: float = 0.8
    spatial_bins: int = 10
    temporal_bins: int = 12
    importance_column: Optional[str] = None

@dataclass
class SamplingResult:
    """Result of data sampling operation"""
    sampled_data: pd.DataFrame
    original_size: int
    sampled_size: int
    sampling_ratio: float
    strategy_used: SamplingStrategy
    quality_score: float
    preserved_extremes: int
    execution_time: float

class DataSampler:
    """Intelligent data sampling for large datasets"""
    
    def __init__(self):
        """Initialize the data sampler"""
        self.sampling_history = []
        self.quality_metrics = {}
    
    def sample_data(self, 
                   data: pd.DataFrame,
                   config: SamplingConfig) -> SamplingResult:
        """
        Sample data using the specified strategy
        
        Args:
            data: DataFrame to sample
            config: Sampling configuration
            
        Returns:
            SamplingResult with sampled data and metadata
        """
        start_time = datetime.now()
        
        try:
            if len(data) <= config.target_size:
                return SamplingResult(
                    sampled_data=data.copy(),
                    original_size=len(data),
                    sampled_size=len(data),
                    sampling_ratio=1.0,
                    strategy_used=config.strategy,
                    quality_score=1.0,
                    preserved_extremes=0,
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
            logger.info(f"Sampling {len(data)} records to {config.target_size} using {config.strategy.value}")
            
            # Apply sampling strategy
            if config.strategy == SamplingStrategy.RANDOM:
                sampled_data = self._random_sampling(data, config)
            elif config.strategy == SamplingStrategy.SYSTEMATIC:
                sampled_data = self._systematic_sampling(data, config)
            elif config.strategy == SamplingStrategy.STRATIFIED:
                sampled_data = self._stratified_sampling(data, config)
            elif config.strategy == SamplingStrategy.TEMPORAL:
                sampled_data = self._temporal_sampling(data, config)
            elif config.strategy == SamplingStrategy.SPATIAL:
                sampled_data = self._spatial_sampling(data, config)
            elif config.strategy == SamplingStrategy.ADAPTIVE:
                sampled_data = self._adaptive_sampling(data, config)
            elif config.strategy == SamplingStrategy.IMPORTANCE:
                sampled_data = self._importance_sampling(data, config)
            else:
                raise ValueError(f"Unknown sampling strategy: {config.strategy}")
            
            # Preserve extremes if requested
            preserved_extremes = 0
            if config.preserve_extremes:
                sampled_data, preserved_extremes = self._preserve_extremes(data, sampled_data, config)
            
            # Preserve recent data if requested
            if config.preserve_recent and 'date' in data.columns:
                sampled_data = self._preserve_recent_data(data, sampled_data, config)
            
            # Remove duplicates and reset index
            sampled_data = sampled_data.drop_duplicates().reset_index(drop=True)
            
            # Ensure we don't exceed target size after adding extremes and recent data
            if len(sampled_data) > config.target_size:
                sampled_data = sampled_data.sample(n=config.target_size, random_state=42).reset_index(drop=True)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(data, sampled_data, config)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = SamplingResult(
                sampled_data=sampled_data,
                original_size=len(data),
                sampled_size=len(sampled_data),
                sampling_ratio=len(sampled_data) / len(data),
                strategy_used=config.strategy,
                quality_score=quality_score,
                preserved_extremes=preserved_extremes,
                execution_time=execution_time
            )
            
            # Store in history
            self.sampling_history.append(result)
            
            logger.info(f"Sampling completed: {len(data)} -> {len(sampled_data)} "
                       f"(ratio: {result.sampling_ratio:.3f}, quality: {quality_score:.3f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in data sampling: {e}")
            # Return original data on error
            return SamplingResult(
                sampled_data=data.copy(),
                original_size=len(data),
                sampled_size=len(data),
                sampling_ratio=1.0,
                strategy_used=config.strategy,
                quality_score=0.0,
                preserved_extremes=0,
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    def _random_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Random sampling strategy"""
        return data.sample(n=config.target_size, random_state=42)
    
    def _systematic_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Systematic sampling strategy"""
        step = len(data) // config.target_size
        indices = range(0, len(data), step)[:config.target_size]
        return data.iloc[indices]
    
    def _stratified_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Stratified sampling based on depth or other numeric column"""
        try:
            # Choose stratification column
            strat_column = None
            for col in ['depth', 'pressure', 'temperature']:
                if col in data.columns:
                    strat_column = col
                    break
            
            if strat_column is None:
                logger.warning("No suitable column for stratification, falling back to random sampling")
                return self._random_sampling(data, config)
            
            # Create strata
            data_copy = data.copy()
            data_copy['stratum'] = pd.cut(data_copy[strat_column], bins=10, labels=False)
            
            # Sample from each stratum
            points_per_stratum = config.target_size // 10
            sampled_parts = []
            
            for stratum in range(10):
                stratum_data = data_copy[data_copy['stratum'] == stratum]
                if len(stratum_data) > 0:
                    n_sample = min(len(stratum_data), points_per_stratum)
                    if n_sample > 0:
                        sampled_parts.append(stratum_data.sample(n=n_sample, random_state=42))
            
            if sampled_parts:
                sampled = pd.concat(sampled_parts, ignore_index=True)
                sampled = sampled.drop('stratum', axis=1)
                
                # Ensure we don't exceed target size
                if len(sampled) > config.target_size:
                    sampled = sampled.sample(n=config.target_size, random_state=42)
                
                return sampled
            else:
                return self._random_sampling(data, config)
                
        except Exception as e:
            logger.warning(f"Error in stratified sampling: {e}")
            return self._random_sampling(data, config)
    
    def _temporal_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Temporal sampling strategy"""
        try:
            if 'date' not in data.columns:
                logger.warning("No date column for temporal sampling, falling back to random")
                return self._random_sampling(data, config)
            
            # Convert date column
            data_copy = data.copy()
            data_copy['date'] = pd.to_datetime(data_copy['date'])
            
            # Create temporal bins
            date_range = data_copy['date'].max() - data_copy['date'].min()
            bin_size = date_range / config.temporal_bins
            
            data_copy['time_bin'] = ((data_copy['date'] - data_copy['date'].min()) / bin_size).astype(int)
            data_copy['time_bin'] = data_copy['time_bin'].clip(0, config.temporal_bins - 1)
            
            # Sample from each time bin
            points_per_bin = config.target_size // config.temporal_bins
            sampled_parts = []
            
            for bin_val in range(config.temporal_bins):
                bin_data = data_copy[data_copy['time_bin'] == bin_val]
                if len(bin_data) > 0:
                    n_sample = min(len(bin_data), points_per_bin)
                    if n_sample > 0:
                        sampled_parts.append(bin_data.sample(n=n_sample, random_state=42))
            
            if sampled_parts:
                sampled = pd.concat(sampled_parts, ignore_index=True)
                return sampled.drop('time_bin', axis=1)
            else:
                return self._random_sampling(data, config)
                
        except Exception as e:
            logger.warning(f"Error in temporal sampling: {e}")
            return self._random_sampling(data, config)
    
    def _spatial_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Spatial sampling strategy"""
        try:
            if 'latitude' not in data.columns or 'longitude' not in data.columns:
                logger.warning("No spatial columns for spatial sampling, falling back to random")
                return self._random_sampling(data, config)
            
            data_copy = data.copy()
            
            # Create spatial grid
            lat_bins = np.linspace(data_copy['latitude'].min(), data_copy['latitude'].max(), 
                                 int(np.sqrt(config.spatial_bins)) + 1)
            lon_bins = np.linspace(data_copy['longitude'].min(), data_copy['longitude'].max(), 
                                 int(np.sqrt(config.spatial_bins)) + 1)
            
            data_copy['lat_bin'] = pd.cut(data_copy['latitude'], bins=lat_bins, labels=False)
            data_copy['lon_bin'] = pd.cut(data_copy['longitude'], bins=lon_bins, labels=False)
            data_copy['spatial_bin'] = data_copy['lat_bin'] * len(lon_bins) + data_copy['lon_bin']
            
            # Sample from each spatial bin
            unique_bins = data_copy['spatial_bin'].dropna().unique()
            points_per_bin = max(1, config.target_size // len(unique_bins))
            
            sampled_parts = []
            for bin_val in unique_bins:
                bin_data = data_copy[data_copy['spatial_bin'] == bin_val]
                if len(bin_data) > 0:
                    n_sample = min(len(bin_data), points_per_bin)
                    if n_sample > 0:
                        sampled_parts.append(bin_data.sample(n=n_sample, random_state=42))
            
            if sampled_parts:
                sampled = pd.concat(sampled_parts, ignore_index=True)
                return sampled.drop(['lat_bin', 'lon_bin', 'spatial_bin'], axis=1)
            else:
                return self._random_sampling(data, config)
                
        except Exception as e:
            logger.warning(f"Error in spatial sampling: {e}")
            return self._random_sampling(data, config)
    
    def _adaptive_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Adaptive sampling based on data characteristics"""
        try:
            # Analyze data characteristics
            has_spatial = 'latitude' in data.columns and 'longitude' in data.columns
            has_temporal = 'date' in data.columns
            has_depth = 'depth' in data.columns
            
            # Choose best strategy based on data
            if has_spatial and has_temporal:
                # Use combined spatial-temporal sampling
                spatial_config = SamplingConfig(
                    strategy=SamplingStrategy.SPATIAL,
                    target_size=config.target_size // 2,
                    preserve_extremes=config.preserve_extremes,
                    spatial_bins=config.spatial_bins
                )
                temporal_config = SamplingConfig(
                    strategy=SamplingStrategy.TEMPORAL,
                    target_size=config.target_size // 2,
                    preserve_extremes=config.preserve_extremes,
                    temporal_bins=config.temporal_bins
                )
                
                spatial_sample = self._spatial_sampling(data, spatial_config)
                temporal_sample = self._temporal_sampling(data, temporal_config)
                
                # Combine samples
                combined = pd.concat([spatial_sample, temporal_sample], ignore_index=True)
                combined = combined.drop_duplicates().reset_index(drop=True)
                
                # If still too large, random sample to target size
                if len(combined) > config.target_size:
                    combined = combined.sample(n=config.target_size, random_state=42)
                
                return combined
                
            elif has_depth:
                return self._stratified_sampling(data, config)
            elif has_temporal:
                return self._temporal_sampling(data, config)
            elif has_spatial:
                return self._spatial_sampling(data, config)
            else:
                return self._random_sampling(data, config)
                
        except Exception as e:
            logger.warning(f"Error in adaptive sampling: {e}")
            return self._random_sampling(data, config)
    
    def _importance_sampling(self, data: pd.DataFrame, config: SamplingConfig) -> pd.DataFrame:
        """Importance sampling based on specified column"""
        try:
            if not config.importance_column or config.importance_column not in data.columns:
                logger.warning("No importance column specified, falling back to random sampling")
                return self._random_sampling(data, config)
            
            data_copy = data.copy()
            importance_col = config.importance_column
            
            # Calculate sampling weights based on importance
            if data_copy[importance_col].dtype in ['object', 'category']:
                # For categorical data, use frequency-based importance
                value_counts = data_copy[importance_col].value_counts()
                # Inverse frequency weighting (rare values get higher weight)
                weights = data_copy[importance_col].map(lambda x: 1.0 / value_counts[x])
            else:
                # For numeric data, use absolute deviation from mean
                mean_val = data_copy[importance_col].mean()
                weights = np.abs(data_copy[importance_col] - mean_val)
                weights = weights / weights.sum()  # Normalize
            
            # Sample based on weights
            sampled_indices = np.random.choice(
                data_copy.index,
                size=config.target_size,
                replace=False,
                p=weights / weights.sum()
            )
            
            return data_copy.loc[sampled_indices]
            
        except Exception as e:
            logger.warning(f"Error in importance sampling: {e}")
            return self._random_sampling(data, config)
    
    def _preserve_extremes(self, 
                          original_data: pd.DataFrame,
                          sampled_data: pd.DataFrame,
                          config: SamplingConfig) -> Tuple[pd.DataFrame, int]:
        """Preserve extreme values in the sample"""
        try:
            numeric_columns = original_data.select_dtypes(include=[np.number]).columns
            preserved_count = 0
            
            # Limit the number of extremes to preserve (max 10% of target size)
            max_extremes = max(2, int(config.target_size * 0.1))
            extremes_added = 0
            
            for col in numeric_columns:
                if col in original_data.columns and extremes_added < max_extremes:
                    # Find extreme values
                    min_idx = original_data[col].idxmin()
                    max_idx = original_data[col].idxmax()
                    
                    # Add extremes if not already in sample and we haven't exceeded limit
                    if min_idx not in sampled_data.index and extremes_added < max_extremes:
                        sampled_data = pd.concat([sampled_data, original_data.loc[[min_idx]]], 
                                               ignore_index=True)
                        preserved_count += 1
                        extremes_added += 1
                    
                    if max_idx not in sampled_data.index and extremes_added < max_extremes:
                        sampled_data = pd.concat([sampled_data, original_data.loc[[max_idx]]], 
                                               ignore_index=True)
                        preserved_count += 1
                        extremes_added += 1
            
            return sampled_data, preserved_count
            
        except Exception as e:
            logger.warning(f"Error preserving extremes: {e}")
            return sampled_data, 0
    
    def _preserve_recent_data(self, 
                            original_data: pd.DataFrame,
                            sampled_data: pd.DataFrame,
                            config: SamplingConfig) -> pd.DataFrame:
        """Preserve recent data points"""
        try:
            if 'date' not in original_data.columns:
                return sampled_data
            
            # Get recent data (last 10% of time range)
            date_col = pd.to_datetime(original_data['date'])
            date_range = date_col.max() - date_col.min()
            recent_threshold = date_col.max() - date_range * 0.1
            
            recent_data = original_data[date_col >= recent_threshold]
            
            # Limit the number of recent records to preserve (max 5% of target size)
            max_recent = max(1, int(config.target_size * 0.05))
            recent_added = 0
            
            # Add recent data that's not already in sample, up to the limit
            for idx in recent_data.index:
                if idx not in sampled_data.index and recent_added < max_recent:
                    sampled_data = pd.concat([sampled_data, original_data.loc[[idx]]], 
                                           ignore_index=True)
                    recent_added += 1
            
            return sampled_data
            
        except Exception as e:
            logger.warning(f"Error preserving recent data: {e}")
            return sampled_data
    
    def _calculate_quality_score(self, 
                               original_data: pd.DataFrame,
                               sampled_data: pd.DataFrame,
                               config: SamplingConfig) -> float:
        """Calculate quality score for the sampling"""
        try:
            if len(sampled_data) == 0:
                return 0.0
            
            scores = []
            numeric_columns = original_data.select_dtypes(include=[np.number]).columns
            
            for col in numeric_columns:
                if col in sampled_data.columns:
                    # Compare statistical properties
                    orig_mean = original_data[col].mean()
                    samp_mean = sampled_data[col].mean()
                    
                    orig_std = original_data[col].std()
                    samp_std = sampled_data[col].std()
                    
                    # Calculate similarity scores
                    mean_score = 1.0 - abs(orig_mean - samp_mean) / (abs(orig_mean) + 1e-10)
                    std_score = 1.0 - abs(orig_std - samp_std) / (abs(orig_std) + 1e-10)
                    
                    # Range preservation score
                    orig_range = original_data[col].max() - original_data[col].min()
                    samp_range = sampled_data[col].max() - sampled_data[col].min()
                    range_score = min(samp_range, orig_range) / (max(samp_range, orig_range) + 1e-10)
                    
                    col_score = (mean_score + std_score + range_score) / 3
                    scores.append(max(0.0, min(1.0, col_score)))
            
            return sum(scores) / len(scores) if scores else 0.5
            
        except Exception as e:
            logger.warning(f"Error calculating quality score: {e}")
            return 0.5
    
    def recommend_sampling_strategy(self, data: pd.DataFrame, target_size: int) -> SamplingConfig:
        """Recommend optimal sampling strategy based on data characteristics"""
        try:
            # Analyze data characteristics
            has_spatial = 'latitude' in data.columns and 'longitude' in data.columns
            has_temporal = 'date' in data.columns
            has_depth = 'depth' in data.columns
            has_quality = 'quality_flag' in data.columns
            
            data_size = len(data)
            reduction_ratio = target_size / data_size
            
            # Choose strategy based on data characteristics and reduction ratio
            if reduction_ratio > 0.5:
                # Small reduction, use random sampling
                strategy = SamplingStrategy.RANDOM
            elif has_spatial and has_temporal:
                # Rich spatio-temporal data, use adaptive sampling
                strategy = SamplingStrategy.ADAPTIVE
            elif has_depth:
                # Depth data available, use stratified sampling
                strategy = SamplingStrategy.STRATIFIED
            elif has_temporal:
                # Temporal data, use temporal sampling
                strategy = SamplingStrategy.TEMPORAL
            elif has_spatial:
                # Spatial data, use spatial sampling
                strategy = SamplingStrategy.SPATIAL
            else:
                # Default to systematic sampling
                strategy = SamplingStrategy.SYSTEMATIC
            
            # Configure based on data quality
            preserve_extremes = True
            preserve_recent = has_temporal
            quality_threshold = 0.8 if has_quality else 0.5
            
            config = SamplingConfig(
                strategy=strategy,
                target_size=target_size,
                preserve_extremes=preserve_extremes,
                preserve_recent=preserve_recent,
                quality_threshold=quality_threshold,
                spatial_bins=min(20, int(np.sqrt(data_size / 100))),
                temporal_bins=min(24, int(data_size / 1000))
            )
            
            logger.info(f"Recommended sampling strategy: {strategy.value} for {data_size} -> {target_size}")
            
            return config
            
        except Exception as e:
            logger.error(f"Error recommending sampling strategy: {e}")
            return SamplingConfig(
                strategy=SamplingStrategy.RANDOM,
                target_size=target_size
            )
    
    def render_sampling_controls(self) -> SamplingConfig:
        """Render Streamlit controls for sampling configuration"""
        try:
            st.subheader("🎯 Data Sampling Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                strategy = st.selectbox(
                    "Sampling Strategy",
                    options=[s.value for s in SamplingStrategy],
                    index=0,
                    help="Choose the sampling strategy based on your data characteristics"
                )
                
                target_size = st.number_input(
                    "Target Sample Size",
                    min_value=100,
                    max_value=50000,
                    value=10000,
                    step=1000,
                    help="Maximum number of data points to keep"
                )
            
            with col2:
                preserve_extremes = st.checkbox(
                    "Preserve Extreme Values",
                    value=True,
                    help="Keep minimum and maximum values for each numeric column"
                )
                
                preserve_recent = st.checkbox(
                    "Preserve Recent Data",
                    value=True,
                    help="Keep recent data points (requires date column)"
                )
            
            # Advanced options
            with st.expander("Advanced Options"):
                quality_threshold = st.slider(
                    "Quality Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.8,
                    step=0.1,
                    help="Minimum quality score for sampling"
                )
                
                spatial_bins = st.number_input(
                    "Spatial Bins",
                    min_value=4,
                    max_value=50,
                    value=10,
                    help="Number of spatial bins for spatial sampling"
                )
                
                temporal_bins = st.number_input(
                    "Temporal Bins",
                    min_value=4,
                    max_value=50,
                    value=12,
                    help="Number of temporal bins for temporal sampling"
                )
                
                importance_column = st.text_input(
                    "Importance Column",
                    value="",
                    help="Column name for importance sampling (optional)"
                )
            
            return SamplingConfig(
                strategy=SamplingStrategy(strategy),
                target_size=target_size,
                preserve_extremes=preserve_extremes,
                preserve_recent=preserve_recent,
                quality_threshold=quality_threshold,
                spatial_bins=spatial_bins,
                temporal_bins=temporal_bins,
                importance_column=importance_column if importance_column else None
            )
            
        except Exception as e:
            logger.error(f"Error rendering sampling controls: {e}")
            return SamplingConfig(
                strategy=SamplingStrategy.RANDOM,
                target_size=10000
            )
    
    def render_sampling_results(self, result: SamplingResult):
        """Render sampling results in Streamlit"""
        try:
            st.subheader("📊 Sampling Results")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Original Size", f"{result.original_size:,}")
            
            with col2:
                st.metric("Sampled Size", f"{result.sampled_size:,}")
            
            with col3:
                st.metric("Sampling Ratio", f"{result.sampling_ratio:.1%}")
            
            with col4:
                st.metric("Quality Score", f"{result.quality_score:.3f}")
            
            # Additional details
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Strategy Used", result.strategy_used.value)
            
            with col2:
                st.metric("Preserved Extremes", result.preserved_extremes)
            
            with col3:
                st.metric("Execution Time", f"{result.execution_time:.2f}s")
            
            # Quality assessment
            if result.quality_score >= 0.8:
                st.success("✅ High quality sampling - statistical properties well preserved")
            elif result.quality_score >= 0.6:
                st.warning("⚠️ Moderate quality sampling - some statistical properties may differ")
            else:
                st.error("❌ Low quality sampling - consider different strategy or larger sample size")
        
        except Exception as e:
            logger.error(f"Error rendering sampling results: {e}")

# Utility functions

def get_data_sampler() -> DataSampler:
    """Get or create data sampler instance"""
    try:
        if hasattr(st.session_state, '__contains__') and 'data_sampler' not in st.session_state:
            st.session_state.data_sampler = DataSampler()
        
        if hasattr(st.session_state, 'data_sampler'):
            return st.session_state.data_sampler
        else:
            return DataSampler()
    except (AttributeError, TypeError):
        # Session state not available (e.g., in tests)
        return DataSampler()