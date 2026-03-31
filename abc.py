import matplotlib
# This forces matplotlib to generate the image in the background without opening a window
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# Data points based on your research parameters
context_lengths = ['10k Tokens', '100k Tokens']
gpt4o_accuracy = [89, 45]
hmanet_accuracy = [89, 82] 

# Set up the figure and axis
plt.figure(figsize=(8, 5))

# Plot the lines with institute-themed colors
plt.plot(context_lengths, gpt4o_accuracy, marker='o', color='#003366', linewidth=2.5, label='GPT-4o (Baseline)') 
plt.plot(context_lengths, hmanet_accuracy, marker='s', color='#FF6600', linewidth=2.5, label='HMA-Net') 

# Add data labels directly on the points for clarity
plt.text(0, 89 + 2, '89%', ha='center', color='#003366', fontweight='bold')
plt.text(1, 45 + 2, '45%', ha='center', color='#003366', fontweight='bold')
plt.text(1, 82 + 2, '82%', ha='center', color='#FF6600', fontweight='bold')

# Formatting the graph
plt.title('Performance Degradation in Long-Context Reasoning', fontsize=14, fontweight='bold', pad=15)
plt.ylabel('Accuracy (%)', fontsize=12)
plt.xlabel('Context Length', fontsize=12)
plt.ylim(30, 100)
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend(loc='lower left', fontsize=11)

# Save the plot as a high-resolution, downloadable image
plt.tight_layout()
plt.savefig('HMA_Net_Performance.png', dpi=300)
print("Graph successfully saved as HMA_Net_Performance.png!")