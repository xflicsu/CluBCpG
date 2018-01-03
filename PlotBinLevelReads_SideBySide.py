from ParseBam import BamFileReadParser
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import sys
import os

sns.set_context("talk")
sns.set_style("darkgrid")


class TrackAndOutputStats:
    """This class should implement functions to be passed matrices, perform calculations, store these stats,
    and finally implement a function to write the output of all this stored data to a file"""

    def __init__(self, output_loc: str):
        # empty lists to store the data calculated
        self.output_loc = output_loc
        self.bin_name_for_average= []
        self.avg_methylation_matrix_A = []
        self.avg_methylation_matrix_B = []

    def calculate_avg_methylation(self, matrix_A, matrix_X, chromosome: str, stop_pos: int):
        # Take matrixes, calculate avg methylation for each row, calculate total avg, store data
        pass

    def write_avg_methylation(self):
        # Take data stored in self, generate output file, write to disk
        pass



def plot_complete_bin_reads(matrix_A, matrix_B, chromosome: str, start_pos: int, stop_pos: int, output_loc: str):
    # Take a martix of CpG status and plot
    # Visualze the reads from the bam file, 1=methylated, 0=unmethylated

    f, axarr = plt.subplots(1, 2, figsize=(15,5))

    g = sns.heatmap(matrix_A, vmax=1, vmin=0, cmap='coolwarm', linewidths=0.1, ax=axarr[0], )
    g.set_title("{} {}: {}-{}".format("A\n", chromosome, start_pos, stop_pos))
    g.set_ylabel("reads")
    g.set_xlabel("CpG site")

    h = sns.heatmap(matrix_B, vmax=1, vmin=0, cmap='coolwarm', linewidths=0.1, ax=axarr[1])
    h.set_title("{} {}: {}-{}".format("B\n", chromosome, start_pos, stop_pos))
    h.set_ylabel("reads")
    h.set_xlabel("CpG site")

    file_name = "{}_{}.png".format(chromosome, str(stop_pos))
    output_file = os.path.join(output_loc, file_name)
    plt.savefig(output_file)
    plt.close()


if __name__ == "__main__":
    # Get arguments from the command line
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("bins_to_plot",
                            help="File with each line being one bin to extract and plot, "
                                 "bins should be in format: chr19:3333333")
    arg_parser.add_argument("-a", "--input_bam_A",
                            help="First Input bam file, coordinate sorted with index present")
    arg_parser.add_argument("-b", "--input_bam_B",
                            help="Second Input bam file, coordinate sorted with index present")
    arg_parser.add_argument("-o", "--output_dir",
                            help="Output directory to save figures, defaults to bam file loaction",)

    args = arg_parser.parse_args()

    # Set output directory to user input or default
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.dirname(args.input_bam_A)

    print("Output directory set to {}".format(output_dir))
    file_spec_path = os.path.join(output_dir, "plots_{}".format(os.path.basename(os.path.splitext(args.input_bam_A)[0])))

    # Create subdirectory for plots
    if not os.path.exists(file_spec_path):
        print("Creating file specific plots folder in output directory")
        os.makedirs(file_spec_path)
    else:
        print("plots folder already exists, saving there...")

    # write out inputs for reference
    print("Input bam file is: {}".format(args.input_bam_A))
    print("List of bins is: {}".format(args.bins_to_plot))
    print("Plots being saved to {}".format(file_spec_path))
    sys.stdout.flush()

    # Load bins into memory
    bins = []
    with open(args.bins_to_plot, 'r') as f:
        for line in f:
            bins.append(line.strip())

    # Create bam file parser object
    bam_parser_A = BamFileReadParser(args.input_bam_A, 20)
    bam_parser_B = BamFileReadParser(args.input_bam_B, 20)


    # loop over bins generating a matrix for each
    for bin in bins:
        bin_chr = bin.split("_")
        chromosome = bin_chr[0]
        stop_pos = int(bin_chr[1])

        reads_A = bam_parser_A.parse_reads(chromosome, stop_pos-100, stop_pos)
        matrix_A = bam_parser_A.create_matrix(reads_A)
        matrix_A = matrix_A.dropna()

        reads_B = bam_parser_B.parse_reads(chromosome, stop_pos-100, stop_pos)
        matrix_B = bam_parser_B.create_matrix(reads_B)
        matrix_B = matrix_B.dropna()

        # plot the matrix
        plot_complete_bin_reads(matrix_A, matrix_B, chromosome, stop_pos-100, stop_pos, file_spec_path)

