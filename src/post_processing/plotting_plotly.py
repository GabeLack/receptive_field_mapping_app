import warnings
from scipy.stats import gaussian_kde
import tempfile
import imageio.v2 as imageio  # newer version
from src.components.validation import Validation as Val
from src.post_processing.datadlc import DataDLC
from src.post_processing.mergeddata import MergedData
import cv2
from sklearn.preprocessing import MinMaxScaler
from matplotlib.lines import Line2D
from matplotlib.animation import FuncAnimation
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
import os
import seaborn as sns
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

#! Make futurewarnings and runtimewarnings quiet for now
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


class PlottingPlotly():
    """
    A class providing static methods for advanced plotting and video generation
    for post-processing and visualization of behavioral and neural data.

    This class includes methods to:
        - Generate interactive and static plots using Plotly and Matplotlib.
        - Create animated videos of homography, labeled tracking, and scrolling signals.
        - Visualize receptive field mapping, KDE density, and scatter plots.
        - Overlay video frames and homography outlines on plots.
        - Validate input types, shapes, and file paths for robust plotting.

    Typical usage involves calling the static methods directly, passing in
    processed data (e.g., from MergedData or DataDLC), homography points,
    and relevant plotting parameters.

    Methods:
        - plot_dual_y_axis: Plot two signals with dual y-axes using Plotly.
        - generate_labeled_video: Create a video with labeled tracking points.
        - generate_homography_video: Animate homography transformation over time.
        - plot_homography_interactive: Interactive animation of homography points.
        - plot_rf_mapping_animated: Animated receptive field mapping video.
        - _compute_kde: Compute 2D kernel density estimate for scatter data.
        - plot_kde_density_interactive: Interactive KDE density plot with Plotly.
        - plot_scatter_interactive: Interactive scatter plot with homography overlay.
        - background_framing: Overlay video frames and homography on Matplotlib axes.
        - plot_kde_density: Static KDE density plot with optional video background.
        - plot_scatter: Static scatter plot with homography and video overlay.
        - generate_scroll_over_video: Create a scrolling plot video synchronized with video frames.

    All methods are static and require explicit input arguments.

    Raises:
        TypeError, ValueError: For invalid input types, shapes, or file paths.

    Example:
        fig = PlottingPlotly.plot_scatter_interactive(
            merged_data, x_col="x", y_col="y", homography_points=points,
            size_col="size", color_col="Spike"
        )
    """
    @staticmethod
    def _get_lim(homography_points: np.ndarray = None) -> tuple[int, int]:
        Val.validate_array_int_float(homography_points,
                                     shape=(4, 2),
                                     name="Homography Points")
        diff = (homography_points.max() - homography_points.min())/2
        return homography_points.min() - diff, homography_points.max() + diff

    @staticmethod
    def plot_dual_y_axis(df: pd.DataFrame,
                         columns: list[str],
                         xlabel: str,
                         ylabel_1: str, ylabel_2: str,
                         title: str,
                         color_1: str = "#1f77b4",  # blue
                         color_2: str = "#d62728",   # red
                         invert_y_2: bool = False
                         ) -> go.Figure:
        """
        Plot two signals with dual y-axes using Plotly.

        Args:
            df (pd.DataFrame): DataFrame containing the data.
            x_col (str): Name of the x-axis column.
            y1_col (str): Name of the first y-axis column.
            y2_col (str): Name of the second y-axis column.
            y1_label (str): Label for the first y-axis.
            y2_label (str): Label for the second y-axis.
            title (str): Plot title.

        Returns:
            plotly.graph_objs.Figure: The resulting Plotly figure.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(columns, list, "Columns")
        Val.validate_type_in_list(columns, str, "Columns")
        Val.validate_dataframe(df, required_columns=columns, name="DataFrame")
        Val.validate_strings(xlabel=xlabel, ylabel_1=ylabel_1, ylabel_2=ylabel_2,
                             title=title, color_1=color_1, color_2=color_2)

        try:
            # Create the figure
            fig = go.Figure()

            # Plot the first column (primary y-axis)
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[columns[0]],
                    name=ylabel_1,
                    line=dict(color=color_1),
                    yaxis="y1"
                )
            )

            # Plot the second column (secondary y-axis)
            second_y_data = -df[columns[1]] if invert_y_2 else df[columns[1]]
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=second_y_data,
                    name=ylabel_2,
                    line=dict(color=color_2),
                    yaxis="y2"
                )
            )

            # Update layout
            fig.update_layout(
                title=dict(text=title, x=0.5),
                xaxis=dict(title=xlabel),
                yaxis=dict(
                    title=dict(text=ylabel_1, font=dict(color=color_1)),
                    tickfont=dict(color=color_1),
                    zeroline=True,  # Ensure the x-axis is visible
                    zerolinecolor="black",
                    zerolinewidth=2
                ),
                yaxis2=dict(
                    title=dict(text=ylabel_2, font=dict(color=color_2)),
                    tickfont=dict(color=color_2),
                    overlaying="y",  # Overlay on the same plot
                    side="right",    # Place ticks on the right side
                    zeroline=True,   # Ensure the x-axis is visible
                    zerolinecolor="black",
                    zerolinewidth=2
                ),
                legend=dict(
                    x=1.05, y=1,
                    traceorder="normal",
                    orientation="v",
                    font=dict(size=12)
                ),
                margin=dict(t=50, b=60)
            )

            return fig

        except Exception as e:
            raise Exception(f"Error generating dual-axis Plotly chart: {e}")

    @staticmethod
    def generate_labeled_video(dlc_data: DataDLC,
                            video_path: str,
                            square_cmap: str = "Accent",
                            filament_cmap: str = "Blues") -> bytes:
        """
        Generate a video with labeled tracking points overlaid on video frames.

        Args:
            df (pd.DataFrame): DataFrame with tracking data.
            video_path (str): Path to the input video file.
            output_path (str): Path to save the output video.
            columns (list of str): List of columns to plot as points.
            colors (list of str): List of colors for each point.
            fps (int): Frames per second for output video.
            codec (str): Video codec to use.

        Returns:
            bytes: The video as a byte stream.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(dlc_data, DataDLC, "DLC Data")
        Val.validate_path(video_path, file_types=[".mp4", ".avi"])
        Val.validate_path_exists(video_path)
        Val.validate_strings(square_cmap=square_cmap, filament_cmap=filament_cmap)

        # Extract data
        df_square = dlc_data.df_square.copy()
        df_monofil = dlc_data.df_monofil.copy()

        # Open the video
        cap = cv2.VideoCapture(video_path)
        frame_rate = int(cap.get(cv2.CAP_PROP_FPS))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Get Matplotlib colormaps
        square_colors = plt.get_cmap(square_cmap)(np.linspace(0, 1, len(df_square.columns) // 2))
        filament_colors = plt.get_cmap(filament_cmap)(np.linspace(0, 1, len(df_monofil.columns) // 2))

        # Convert colors to BGR and scale to 0–255
        square_colors = [(int(c[2] * 255), int(c[1] * 255), int(c[0] * 255)) for c in square_colors]
        filament_colors = [(int(c[2] * 255), int(c[1] * 255), int(c[0] * 255)) for c in filament_colors]

        # Use imageio writer with proper codec
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmpfile:
            temp_path = tmpfile.name

        writer = imageio.get_writer(temp_path, fps=frame_rate, codec='libx264')

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Draw square points
            for i in range(len(df_square.columns) // 2):  # Assuming x, y pairs
                x = int(df_square.iloc[frame_idx, i * 2])
                y = int(df_square.iloc[frame_idx, i * 2 + 1])
                color = square_colors[i]  # Use precomputed BGR color
                cv2.circle(frame, (x, y), radius=5, color=color, thickness=-1)

            # Draw filament points
            for i in range(len(df_monofil.columns) // 2):  # Assuming x, y pairs
                x = int(df_monofil.iloc[frame_idx, i * 2])
                y = int(df_monofil.iloc[frame_idx, i * 2 + 1])
                color = filament_colors[i]  # Use precomputed BGR color
                cv2.circle(frame, (x, y), radius=5, color=color, thickness=-1)

            # Convert frame to RGB for imageio
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            writer.append_data(frame_rgb)

            frame_idx += 1

        cap.release()
        writer.close()

        # Return the video as bytes
        with open(temp_path, "rb") as f:
            return f.read()

    @staticmethod
    def generate_homography_video(homography_points: np.ndarray,
                                  df_transformed_monofil: pd.DataFrame,
                                  fps: int = 30,
                                  title: str = "Homography Animation",
                                  x_label: str = "x (mm)",
                                  y_label: str = "y (mm)",
                                  color: str = "#d62728",
                                  figsize: tuple[int] = (12, 12)) -> bytes:
        """
        Create an animated video showing the homography transformation over time.

        Args:
            homography_points (np.ndarray): Array of homography points (4, 2).
            df_transformed_monofil (pd.DataFrame): DataFrame with transformed points.
            fps (int): Frames per second for the video.
            title (str): Title for the animation.
            x_label (str): X-axis label.
            y_label (str): Y-axis label.
            color (str): Color for the plot.
            figsize (tuple): Figure size (width, height).

        Returns:
            bytes: The video as a byte stream.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_type(df_transformed_monofil, pd.DataFrame,
                          "Transformed Monofilament Data")
        Val.validate_positive(fps, "FPS", zero_allowed=False)
        Val.validate_strings(title=title, x_label=x_label,
                             y_label=y_label, color=color)
        Val.validate_type(figsize, tuple, "Figure Size")

        fig, ax = plt.subplots(figsize=figsize)
        ax.set_xlim(PlottingPlotly._get_lim(homography_points))
        ax.set_ylim(PlottingPlotly._get_lim(homography_points))
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        for point in homography_points:
            ax.axhline(y=point[1], color='gray', linestyle='--', alpha=0.5)
            ax.axvline(x=point[0], color='gray', linestyle='--', alpha=0.5)

        line, = ax.plot([], [], 'bo-', color=color)

        def init():
            line.set_data([], [])
            return line,

        def update(frame):
            points = df_transformed_monofil.iloc[frame].values.reshape(-1, 2)
            line.set_data(points[:, 0], points[:, 1])
            return line,

        anim = FuncAnimation(fig, update, frames=len(df_transformed_monofil),
                             init_func=init, blit=True, interval=1000 / fps)

        # Save to a temp file and return bytes
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        anim.save(temp_file.name, fps=fps, extra_args=['-vcodec', 'libx264'])

        with open(temp_file.name, "rb") as f:
            video_bytes = f.read()
        return video_bytes

    @staticmethod
    def plot_homography_interactive(homography_points: np.ndarray,
                                    df_transformed_monofil: pd.DataFrame,
                                    title="Homography Animation",
                                    color="royalblue",
                                    x_label="x (mm)",
                                    y_label="y (mm)") -> go.Figure:
        """
        Generate an interactive Plotly animation of homography points.

        Args:
            homography_points (np.ndarray): Array of homography points (4, 2).
            df_transformed_monofil (pd.DataFrame): DataFrame with transformed points.
            title (str): Plot title.
            color (str): Line and marker color.
            x_label (str): X-axis label.
            y_label (str): Y-axis label.

        Returns:
            plotly.graph_objs.Figure: The interactive Plotly figure.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_type(df_transformed_monofil, pd.DataFrame,
                          "Transformed Monofilament Data")
        Val.validate_strings(title=title, color=color,
                             x_label=x_label, y_label=y_label)

        # Create frames
        frames = []
        for i in range(len(df_transformed_monofil)):
            points = df_transformed_monofil.iloc[i].values.reshape(-1, 2)
            frames.append(go.Frame(
                data=[
                    go.Scatter(
                        x=points[:, 0],
                        y=points[:, 1],
                        mode='lines+markers',
                        line=dict(color=color),
                        marker=dict(size=6)
                    )
                ],
                name=str(i)
            ))

        # Get overall frame to define layout
        init_points = df_transformed_monofil.iloc[0].values.reshape(-1, 2)

        # Layout
        layout = go.Layout(
            title=title,
            title_x=0.5,
            xaxis=dict(title=x_label,
                       range=PlottingPlotly._get_lim(homography_points),
                       showgrid=False, zeroline=False),
            yaxis=dict(title=y_label,
                       range=PlottingPlotly._get_lim(homography_points),
                       showgrid=False, zeroline=False),
            updatemenus=[dict(
                type='buttons',
                showactive=False,
                y=1.05,
                x=1.15,
                xanchor='right',
                yanchor='top',
                buttons=[
                    dict(label='Play',
                         method='animate',
                         args=[None,
                               {"frame": {"duration": 100,
                                          "redraw": True},
                                "fromcurrent": True}]),
                    dict(label='Pause',
                         method='animate',
                         args=[[None],
                               {"frame": {"duration": 0},
                                "mode": "immediate",
                                "transition": {"duration": 0}
                                }])
                ]
            )],
            sliders=[dict(
                steps=[dict(
                    method='animate',
                    args=[[str(i)],
                          {"frame": {"duration": 0, "redraw": True},
                              "mode": "immediate"}
                          ], label=str(i)) for i in range(len(frames))],
                transition=dict(duration=0),
                x=0, y=0,
                currentvalue=dict(prefix="Frame: ", visible=True),
                len=1.0
            )]
        )

        # Combine into figure
        fig = go.Figure(
            data=[go.Scatter(x=init_points[:, 0], y=init_points[:, 1],
                             mode='lines+markers',
                             line=dict(color=color),
                             marker=dict(size=6))],
            layout=layout,
            frames=frames
        )

        # Add reference lines for homography box
        for pt in homography_points:
            fig.add_shape(type="line",
                          x0=pt[0], x1=pt[0],
                          y0=PlottingPlotly._get_lim(homography_points)[0],
                          y1=PlottingPlotly._get_lim(homography_points)[1],
                          line=dict(dash="dash", color="gray", width=1))
            fig.add_shape(type="line",
                          x0=PlottingPlotly._get_lim(homography_points)[0],
                          x1=PlottingPlotly._get_lim(homography_points)[1],
                          y0=pt[1], y1=pt[1],
                          line=dict(dash="dash", color="gray", width=1))

        return fig

    @staticmethod
    def plot_rf_mapping_animated(merged_data: MergedData,
                                 x_col: str, y_col: str,
                                 homography_points: np.ndarray,
                                 size_col: str,
                                 color_col: str,
                                 title: str = "RF Mapping Animation",
                                 bending: bool = False,
                                 spikes: bool = False,
                                 xlabel: str = "x (mm)",
                                 ylabel: str = "y (mm)",
                                 fps: int = 30,
                                 figsize: tuple[int] = (12, 12),
                                 cmap: str = "viridis") -> bytes:
        """
        Create an animated video visualizing receptive field mapping.

        Args:
            merged_data (MergedData): The merged data object.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            homography_points (np.ndarray): Array of homography points (4, 2).
            size_col (str): Column for marker size.
            color_col (str): Column for marker color.
            title (str): Plot title.
            bending (bool): Whether to use bending threshold.
            spikes (bool): Whether to use spikes threshold.
            xlabel (str): X-axis label.
            ylabel (str): Y-axis label.
            fps (int): Frames per second for the video.
            figsize (tuple): Figure size (width, height).
            cmap (str): Colormap name.

        Returns:
            bytes: The video as a byte stream.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(merged_data, MergedData, "MergedData")
        Val.validate_strings(x_col=x_col, y_col=y_col, size_col=size_col, color_col=color_col,
                             title=title, xlabel=xlabel, ylabel=ylabel, cmap=cmap)
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_type(bending, bool, "Bending")
        Val.validate_type(spikes, bool, "Spikes")
        Val.validate_positive(fps, "FPS", zero_allowed=False)
        Val.validate_type(figsize, tuple, "Figure Size")

        df = merged_data.threshold_data(bending, spikes)

        # Normalize size and color
        scaler = MinMaxScaler(feature_range=(1, 30))
        df["scaled_size"] = scaler.fit_transform(df[[size_col]]) * 5

        if color_col == "Spike":
            color_map = df["Spike"].apply(
                lambda x: 'blue' if x > 0 else 'grey')
        else:
            # Try to get the colormap directly by name (from matplotlib or plotly-compatible strings)
            try:
                resolved_cmap = plt.get_cmap(cmap)
            except ValueError:
                raise ValueError(
                    f"{cmap} is not a recognized Matplotlib colormap.")

            color_norm = plt.Normalize(df[color_col].min(),
                                       df[color_col].max())
            color_mapper = plt.cm.ScalarMappable(norm=color_norm,
                                                 cmap=resolved_cmap)
            color_map = color_mapper.to_rgba(df[color_col])

        # Set up video writer
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmpfile:
            temp_path = tmpfile.name

        writer = imageio.get_writer(temp_path, fps=fps, codec='libx264')

        # Before loop
        history_x, history_y, history_size, history_color = [], [], [], []

        # Inside loop
        for frame_idx in range(len(df)):
            fig, ax = plt.subplots(figsize=figsize)
            ax.set_xlim(PlottingPlotly._get_lim(homography_points))
            ax.set_ylim(PlottingPlotly._get_lim(homography_points))
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)

            # Homography lines
            for point in homography_points:
                ax.axhline(y=point[1], color='gray', linestyle='--', alpha=0.5)
                ax.axvline(x=point[0], color='gray', linestyle='--', alpha=0.5)

            # Append current frame data to history
            current_row = df.iloc[frame_idx]
            history_x.append(current_row[x_col])
            history_y.append(current_row[y_col])
            history_size.append(current_row["scaled_size"])
            history_color.append(
                color_map[frame_idx] if color_col != "Spike" else color_map.iloc[frame_idx]
            )

            # Plot all points up to current frame
            ax.scatter(history_x, history_y, s=history_size, c=history_color,
                       alpha=0.7, edgecolors=None)

            # Add legend or colorbar
            if color_col == "Spike":
                legend_elements = [
                    Line2D([0], [0], marker='o', color='w',
                           markerfacecolor='blue', markersize=10,
                           label='Spike'),
                    Line2D([0], [0], marker='o', color='w',
                           markerfacecolor='grey', markersize=10,
                           label='No Spike')
                ]
                ax.legend(handles=legend_elements, loc="upper left",
                          title=f"Spike Status\n Circle Size ∝ {size_col}")
            else:
                ax.legend(loc="upper left",
                          title=f"Circle Size ∝ {size_col}")
                cbar = fig.colorbar(color_mapper, ax=ax)
                cbar.set_label(f'{color_col} (Color)')

            # Convert Matplotlib figure to an image
            fig.canvas.draw()
            frame = np.array(fig.canvas.renderer.buffer_rgba())
            plt.close(fig)

            # Write the frame to the video
            writer.append_data(frame)

        writer.close()

        # Return video bytes
        with open(temp_path, "rb") as f:
            return f.read()

    @staticmethod
    def _compute_kde(df: pd.DataFrame,
                     x_col: str, y_col: str,
                     grid_limits: tuple,
                     bw_method: float = 0.2):
        """
        Compute a 2D kernel density estimate (KDE) for scatter data.

        Args:
            df (pd.DataFrame): DataFrame containing the data.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            grid_limits (tuple): (xmin, xmax, ymin, ymax) for the KDE grid.
            bw_method (float): Bandwidth method for KDE.

        Returns:
            tuple: (xx, yy, zz) meshgrid arrays for plotting.

        Raises:
            KeyError, ValueError: If columns or grid limits are invalid.
        """
        xmin, xmax, ymin, ymax = grid_limits
        xx, yy = np.mgrid[xmin:xmax:200j, ymin:ymax:200j]
        positions = np.vstack([xx.ravel(), yy.ravel()])
        values = np.vstack([df[x_col].values, df[y_col].values])
        kernel = gaussian_kde(values, bw_method=bw_method)
        zz = np.reshape(kernel(positions).T, xx.shape)
        return xx, yy, zz

    @staticmethod
    def plot_kde_density_interactive(merged_data: MergedData,
                         x_col: str, y_col: str,
                         homography_points: np.ndarray,
                         bending: bool = False,
                         spikes: bool = False,
                         bw_bending: float = 0.2,
                         bw_spikes: float = 0.2,
                         title: str = 'KDE Plot',
                         xlabel: str = 'x (mm)', ylabel: str = 'y (mm)',
                         cmap_bending: str = "Viridis",
                         cmap_spikes: str = "Reds",
                         threshold_percentage: float = 0.05):
        """
        Generate an interactive KDE density plot using Plotly.

        Args:
            merged_data (MergedData): The merged data object.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            homography_points (np.ndarray): Array of homography points (4, 2).
            bending (bool): Whether to plot bending KDE.
            spikes (bool): Whether to plot spikes KDE.
            bw_bending (float): Bandwidth for bending KDE.
            bw_spikes (float): Bandwidth for spikes KDE.
            title (str): Plot title.
            xlabel (str): X-axis label.
            ylabel (str): Y-axis label.
            cmap_bending (str): Colormap for bending KDE.
            cmap_spikes (str): Colormap for spikes KDE.
            threshold_percentage (float): Threshold for density masking.

        Returns:
            plotly.graph_objs.Figure: The interactive Plotly figure.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(merged_data, MergedData, "MergedData")
        Val.validate_strings(x_col=x_col, y_col=y_col,
                             xlabel=xlabel, ylabel=ylabel, title=title,
                             cmap_bending=cmap_bending, cmap_spikes=cmap_spikes)
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_type(bending, bool, "Bending")
        Val.validate_type(spikes, bool, "Spikes")

        # KDE 2D grid limits
        xmin, xmax = PlottingPlotly._get_lim(homography_points)
        ymin, ymax = PlottingPlotly._get_lim(homography_points)
        grid_limits = (xmin, xmax, ymin, ymax)

        # Determine opacity based on conditions
        opacity = 0.5 if bending and spikes else 1.0

        fig = go.Figure()

        # Plot bending KDE
        if bending:
            # Filter bending data
            df_bending = merged_data.threshold_data(bending, False)

            xx, yy, zz_bending = PlottingPlotly._compute_kde(
                df_bending, x_col, y_col, grid_limits, bw_bending)

            # Apply percentage threshold to remove low-density values
            bending_threshold = zz_bending.max() * threshold_percentage
            zz_bending[zz_bending < bending_threshold] = float(
                'nan')  # Mask low-density areas

            fig.add_trace(go.Contour(
                z=zz_bending.T, x=xx[:, 0], y=yy[0],
                colorscale=cmap_bending,
                showscale=True if not spikes else False,
                contours=dict(showlines=False),
                opacity=opacity,
                name="Bending KDE"
            ))

        # Plot spikes KDE
        if spikes:
            # Filter spikes data
            df_spikes = merged_data.threshold_data(False, spikes)

            xx, yy, zz_spikes = PlottingPlotly._compute_kde(
                df_spikes, x_col, y_col, grid_limits, bw_spikes)

            # Apply percentage threshold to remove low-density values
            spikes_threshold = zz_spikes.max() * threshold_percentage
            zz_spikes[zz_spikes < spikes_threshold] = float(
                'nan')  # Mask low-density areas

            fig.add_trace(go.Contour(
                z=zz_spikes.T, x=xx[:, 0], y=yy[0],
                colorscale=cmap_spikes,
                showscale=True,
                contours=dict(showlines=False),
                opacity=opacity,
                name="Spikes KDE"
            ))

        # Add homography outline
        hp = np.vstack([homography_points, homography_points[0]])  # Close loop
        fig.add_trace(go.Scatter(
            x=hp[:, 0], y=hp[:, 1], mode='lines',
            line=dict(dash='dash', color='gray', width=1),
            name='Homography Bounds'
        ))

        # Update layout
        fig.update_layout(
            title=title,
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            xaxis_range=[xmin, xmax],
            yaxis_range=[ymin, ymax],
            height=600,
            width=600,
            legend=dict(
                x=0,  # Horizontal position (0 = far left, 1 = far right)
                y=1,  # Vertical position (0 = bottom, 1 = top)
                xanchor="left",  # Anchor the legend to the left
                yanchor="top",   # Anchor the legend to the top
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="gray",
                borderwidth=1,
                font=dict(size=8)
            )
        )

        return fig

    @staticmethod
    def plot_scatter_interactive(merged_data: MergedData,
                     x_col: str, y_col: str,
                     homography_points: np.ndarray,
                     size_col: str,
                     color_col: str = None,
                     bending: bool = False,
                     spikes: bool = False,
                     title: str = 'Scatter Plot',
                     xlabel: str = 'x (mm)', ylabel: str = 'y (mm)',
                     cmap: str = 'Viridis'):
        """
        Generate an interactive scatter plot with homography overlay using Plotly.

        Args:
            merged_data (MergedData): The merged data object.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            homography_points (np.ndarray): Array of homography points (4, 2).
            size_col (str): Column for marker size.
            color_col (str, optional): Column for marker color or 'Spikes'.
            bending (bool): Whether to use bending threshold.
            spikes (bool): Whether to use spikes threshold.
            title (str): Plot title.
            xlabel (str): X-axis label.
            ylabel (str): Y-axis label.
            cmap (str): Colormap name.

        Returns:
            plotly.graph_objs.Figure: The interactive Plotly figure.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(merged_data, MergedData, "MergedData")
        Val.validate_strings(x_col=x_col, y_col=y_col, size_col=size_col, color_col=color_col,
                             xlabel=xlabel, ylabel=ylabel, title=title, cmap=cmap)
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_type(bending, bool, "Bending")
        Val.validate_type(spikes, bool, "Spikes")

        df = merged_data.threshold_data(bending, spikes)

        scaler = MinMaxScaler(feature_range=(5, 30))
        scaled_size = scaler.fit_transform(
            df[[size_col]]).flatten()  # Flatten to 1D array

        if color_col == 'Spike':
            df['Color'] = df['Spike'].apply(
                lambda x: 'Spike' if x > 0 else 'No Spike')
            fig = px.scatter(
                df, x=x_col, y=y_col,
                size=scaled_size,
                size_max=7,
                color='Color',
                color_discrete_map={'Spike': 'blue', 'No Spike': 'grey'},
                title=title,
                labels={x_col: xlabel, y_col: ylabel},
                opacity=0.5
            )
        else:
            fig = px.scatter(
                df, x=x_col, y=y_col,
                size=scaled_size,
                size_max=7,
                color=color_col,
                color_continuous_scale=cmap,
                title=title,
                labels={x_col: xlabel, y_col: ylabel,
                        color_col: f'{color_col} (Color)'},
                opacity=0.5
            )
            fig.update_layout(
                coloraxis_colorbar=dict(title=f'{color_col} (Color)')
            )

        # Homography outline
        hp = np.vstack([homography_points, homography_points[0]])  # Close loop
        fig.add_trace(go.Scatter(
            x=hp[:, 0], y=hp[:, 1], mode='lines',
            line=dict(dash='dash', color='gray', width=1),
            name='Homography Bounds'
        ))

        # Set axis limits
        xmin, xmax = PlottingPlotly._get_lim(homography_points)
        ymin, ymax = PlottingPlotly._get_lim(homography_points)
        fig.update_layout(
            xaxis_range=[xmin, xmax],
            yaxis_range=[ymin, ymax],
            height=600,
            width=600,
            legend_title_text=f"Circle Size ∝ {size_col}",
            legend=dict(
                x=0,  y=1,
                xanchor="left",  yanchor="top",
                bgcolor="rgba(255,255,255,0.3)",
                bordercolor="gray",
                borderwidth=1,
                font=dict(size=8)
            ),
            xaxis=dict(
                scaleanchor="y",  # Lock the aspect ratio to make the plot square
                scaleratio=1      # Ensure equal scaling for x and y axes
            )
        )
        return fig

    @staticmethod
    def background_framing(merged_data: MergedData,
                           ax: plt.Axes,
                           homography_points: np.ndarray,
                           video_path: str = None,
                           index: int = None):
        """
        Overlay video frame and homography lines on a Matplotlib axis.

        Args:
            merged_data (MergedData): The merged data object.
            ax (matplotlib.axes.Axes): The axis to draw on.
            homography_points (np.ndarray): Array of homography points (4, 2).
            video_path (str, optional): Path to the video file.
            index (int, optional): Frame index to extract from the video.

        Returns:
            None

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        if video_path is not None and index is not None:
            Val.validate_path(video_path, file_types=[".mp4", ".avi"])
            Val.validate_type(index, int, "Index")
            Val.validate_positive(index, "Index", zero_allowed=True)

            dst_min, dst_max = 300, 500
            dst_points = np.array([[dst_min, dst_max],
                                   [dst_max, dst_max],
                                   [dst_max, dst_min],
                                   [dst_min, dst_min]])
            h_matrix = merged_data.dlc._get_homography_matrix(
                index, dst_points)

            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise ValueError(
                    f"Could not read frame {index} from video {video_path}.")

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = frame.shape
            frame_transformed = cv2.warpPerspective(frame, h_matrix, (w, h))

            pixel_to_mm = 0.1
            frame_width_mm = w * pixel_to_mm
            frame_height_mm = h * pixel_to_mm
            offset_x_mm = -30
            offset_y_mm = -30

            extent = [offset_x_mm,
                      offset_x_mm + frame_width_mm,
                      offset_y_mm + frame_height_mm,
                      offset_y_mm]
            ax.imshow(frame_transformed, extent=extent)

        for point in homography_points:
            ax.axhline(y=point[1], color='gray', linestyle='--', alpha=0.5)
            ax.axvline(x=point[0], color='gray', linestyle='--', alpha=0.5)

    @staticmethod
    def plot_kde_density(merged_data: MergedData,
                         x_col: str, y_col: str,
                         homography_points: np.ndarray,
                         bending: bool = False,
                         spikes: bool = False,
                         title: str = 'KDE Plot',
                         xlabel: str = 'x (mm)', ylabel: str = 'y (mm)',
                         figsize: tuple[int] = (12, 12),
                         cmap="vlag",
                         # Video frame options
                         frame: bool = False,
                         video_path: str = None,
                         index: int = None):
        """
        Generate a static KDE density plot with optional video background.

        Args:
            merged_data (MergedData): The merged data object.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            homography_points (np.ndarray): Array of homography points (4, 2).
            bending (bool): Whether to plot bending KDE.
            spikes (bool): Whether to plot spikes KDE.
            title (str): Plot title.
            xlabel (str): X-axis label.
            ylabel (str): Y-axis label.
            figsize (tuple): Figure size (width, height).
            cmap (str): Colormap name.
            frame (bool): Whether to overlay a video frame.
            video_path (str, optional): Path to the video file.
            index (int, optional): Frame index to extract from the video.

        Returns:
            tuple: (matplotlib.figure.Figure, matplotlib.axes.Axes)

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        Val.validate_type(merged_data, MergedData, "MergedData")
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_strings(x_col=x_col, y_col=y_col,
                             xlabel=xlabel, ylabel=ylabel, title=title,
                             cmap=cmap)
        Val.validate_type(bending, bool, "Bending")
        Val.validate_type(spikes, bool, "Spikes")

        fig, ax = plt.subplots(figsize=figsize)
        PlottingPlotly.background_framing(
            merged_data, ax, homography_points, video_path if frame else None, index if frame else None)

        df = merged_data.threshold_data(bending, spikes)

        sns.kdeplot(x=df[x_col], y=df[y_col],
                    fill=True, cmap=cmap, bw_adjust=0.3, ax=ax, alpha=0.5)

        ax.set_xlim(PlottingPlotly._get_lim(homography_points))
        ax.set_ylim(PlottingPlotly._get_lim(homography_points))
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        plt.show()
        return fig, ax

    @staticmethod
    def plot_scatter(merged_data: MergedData,
                     x_col: str, y_col: str,
                     homography_points: np.ndarray,
                     size_col: str,
                     color_col: str = None,  # New parameter for color mapping
                     bending: bool = False,
                     spikes: bool = False,
                     title: str = 'Scatter Plot',
                     legend_title: str = 'Neuron Spike Status',
                     xlabel: str = 'x (mm)', ylabel: str = 'y (mm)',
                     figsize: tuple[int] = (12, 12),
                     cmap: str = 'viridis',
                     # Video frame options
                     frame: bool = False,
                     video_path: str = None,
                     index: int = None):
        """
        Generate a static scatter plot with homography and optional video overlay.

        Args:
            merged_data (MergedData): The merged data object.
            x_col (str): Name of the x-axis column.
            y_col (str): Name of the y-axis column.
            homography_points (np.ndarray): Array of homography points (4, 2).
            size_col (str): Column for marker size.
            color_col (str, optional): Column for marker color or 'Spikes'.
            bending (bool): Whether to use bending threshold.
            spikes (bool): Whether to use spikes threshold.
            title (str): Plot title.
            legend_title (str): Legend title.
            xlabel (str): X-axis label.
            ylabel (str): Y-axis label.
            figsize (tuple): Figure size (width, height).
            cmap (str): Colormap name.
            frame (bool): Whether to overlay a video frame.
            video_path (str, optional): Path to the video file.
            index (int, optional): Frame index to extract from the video.

        Returns:
            tuple: (matplotlib.figure.Figure, matplotlib.axes.Axes)

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        Val.validate_type(merged_data, MergedData, "MergedData")
        Val.validate_array(homography_points, shape=(4, 2),
                           name="Homography Points")
        Val.validate_strings(x_col=x_col, y_col=y_col,
                             size_col=size_col, color_col=color_col,
                             xlabel=xlabel, ylabel=ylabel,
                             title=title, legend_title=legend_title,
                             cmap=cmap)
        Val.validate_type(bending, bool, "Bending")
        Val.validate_type(spikes, bool, "Spikes")

        fig, ax = plt.subplots(figsize=figsize)
        PlottingPlotly.background_framing(
            merged_data, ax, homography_points, video_path if frame else None, index if frame else None)

        df = merged_data.threshold_data(bending, spikes)

        # Normalize sizes
        norm = plt.Normalize(df[size_col].min(), df[size_col].max())
        sizes = norm(df[size_col]) * 200

        # Handle colors
        if color_col == 'Spike':
            colors = df['Spike'].apply(lambda x: 'blue' if x > 0 else 'grey')
        else:
            color_norm = plt.Normalize(
                df[color_col].min(), df[color_col].max())
            colors = plt.cm.get_cmap(cmap)(color_norm(df[color_col]))

        # Scatter plot
        scatter = ax.scatter(df[x_col], df[y_col],
                             c=colors, s=sizes,
                             alpha=0.5, edgecolors=None, linewidth=0.5)

        # Add legend
        if color_col == 'Spike':
            legend_elements = [
                Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='blue', markersize=10, label='Spike'),
                Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='grey', markersize=10, label='No Spike')
            ]
            ax.legend(handles=legend_elements,
                      loc="upper left",
                      title=f"{legend_title}\n(Circle Size ∝ {size_col})")
        else:
            cbar = fig.colorbar(scatter, ax=ax)
            cbar.set_label(f'{color_col} (Color)')

            # Add a small text box for size correlation
            text_box = f"Circle Size ∝ {size_col}"
            ax.text(0.02, 0.98,
                    text_box,
                    transform=ax.transAxes,
                    fontsize=12,
                    verticalalignment='top',
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.5))

        # Set axis limits and labels
        ax.set_xlim(PlottingPlotly._get_lim(homography_points))
        ax.set_ylim(PlottingPlotly._get_lim(homography_points))
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        plt.show()
        return fig, ax

    @staticmethod
    def generate_scroll_over_video(merged_data: MergedData,
                                   columns: list[str],
                                   video_path: str,
                                   title: str = "Scrolling Plot",
                                   color_1: str = "#1f77b4",
                                   color_2: str = "#d62728") -> bytes:
        """
        Generate a scrolling plot video synchronized with video frames.

        Args:
            merged_data (MergedData): The merged data object.
            columns (list of str): List of column names to plot.
            video_path (str): Path to the video file.
            title (str): Title for the plot.
            color_1 (str): Color for the first signal.
            color_2 (str): Color for the second signal.

        Returns:
            bytes: The video as a byte stream.

        Raises:
            TypeError, ValueError: If input validation fails.
        """
        # Validate inputs
        Val.validate_type(merged_data, MergedData, "Merged Data")
        Val.validate_type_in_list(columns, str, "Columns")
        Val.validate_path(video_path, file_types=[".mp4", ".avi"])
        Val.validate_strings(title=title, color_1=color_1, color_2=color_2)
        Val.validate_path_exists(video_path)

        df_merged = merged_data.df_merged.copy()

        cap = cv2.VideoCapture(video_path)
        frame_rate = int(cap.get(cv2.CAP_PROP_FPS))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        scroll_height = frame_height // 5
        figsize = (frame_width / 100, scroll_height / 100)

        window_size = 100
        frame_idx = 0

        # Use imageio writer with proper codec
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmpfile:
            temp_path = tmpfile.name

        writer = imageio.get_writer(temp_path, fps=frame_rate, codec='libx264')

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            fig_scroll, ax_scroll = plt.subplots(
                len(columns), 1, figsize=figsize, sharex=True)
            if len(columns) == 1:
                ax_scroll = [ax_scroll]

            start_idx = max(0, frame_idx - window_size // 2)
            end_idx = min(len(df_merged), start_idx + window_size)
            data_window = df_merged.iloc[start_idx:end_idx]

            start_xlim = start_idx if start_idx != 0 else frame_idx - 50
            end_xlim = start_xlim + window_size

            line_handles = []
            line_labels = []

            for i, col in enumerate(columns):
                ax = ax_scroll[i]
                ax.clear()
                color = color_1 if i == 0 else color_2

                # Plot the main signal
                line, = ax.plot(data_window.index,
                                data_window[col], label=col, color=color)
                line_handles.append(line)
                line_labels.append(col)

                ax.set_ylim(0, df_merged[col].max())
                ax.set_xlim(start_xlim, end_xlim)
                ax.axvline(frame_idx, color='black', linestyle='--')
                ax.xaxis.set_visible(False)

                # Add threshold line if needed
                if col == "Bending_ZScore":
                    y = merged_data.threshold
                    ax.axhline(y=y, color='grey', linestyle='--')
                    threshold_line = Line2D(
                        [0], [0], color='grey', linestyle='--', label='Threshold')
                    line_handles.append(threshold_line)
                    line_labels.append('Threshold')

            fig_scroll.legend(handles=line_handles,
                              labels=line_labels,
                              loc='center right',
                              ncol=1,
                              fontsize=8)

            fig_scroll.suptitle(title, fontsize=12)
            fig_scroll.canvas.draw()
            scroll_img = np.array(
                fig_scroll.canvas.renderer.buffer_rgba())[:, :, :3]
            plt.close(fig_scroll)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            combined_frame = np.vstack((scroll_img, frame_rgb))
            writer.append_data(combined_frame)

            frame_idx += 1

        cap.release()
        writer.close()

        with open(temp_path, "rb") as f:
            return f.read()
