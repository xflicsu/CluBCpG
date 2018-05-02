from sklearn.cluster import DBSCAN
from collections import Counter
import pandas as pd
from pandas.core.indexes.base import InvalidIndexError
import numpy as np
import sys
import logging
import os
from ParseBam import BamFileReadParser
from OutputComparisonResults import OutputIndividualMatrixData
import argparse
import datetime
from multiprocessing import Pool

# HELPER METHODS


# Remove clusters with less than n members
def filter_data_frame(matrix: pd.DataFrame, cluster_memeber_min):
    output = matrix.copy()
    for cluster in output['class'].unique():
        df = output[output['class'] == cluster]
        if len(df) < cluster_memeber_min:
            indexes = df.index
            output.drop(indexes, inplace=True)

    return output


# Get only the matrices made up of reads from A OR B
def get_unique_matrices(filtered_matrix):
    unique_dfs = []
    for label in filtered_matrix['class'].unique():
        df = filtered_matrix[filtered_matrix['class'] == label]
        if len(df['input'].unique()) == 1:
            unique_dfs.append(df)

    return unique_dfs


# Get matrices with reads made up of A AND B
def get_common_matrices(filtered_matrix):
    shared_dfs = []
    for label in filtered_matrix['class'].unique():
        df = filtered_matrix[filtered_matrix['class'] == label]
        if len(df['input'].unique()) > 1:
            shared_dfs.append(df)

    return shared_dfs

# Get the means for all unique matrices
def get_unique_means(filtered_matrix):
    output = []
    for matrix in get_unique_matrices(filtered_matrix):
        input_file = matrix['input'].unique()[0]
        matrix_mean = np.array(matrix)[:, :-2].mean()
        output.append((input_file, matrix_mean))

    return output


# Get the means for all common matrices
def get_common_means(filtered_matrix):
    output = []
    for matrix in get_common_matrices(filtered_matrix):
        matrix_mean = np.array(matrix)[:, :-2].mean()
        output.append(matrix_mean)

    return output


# Generate a string label for each bin
def make_bin_label(chromosome, stop_loc):
    return "_".join([chromosome, str(stop_loc)])


# Takes the output of process_bins() and converts it into list of lines of data for output
def generate_individual_matrix_data(filtered_matrix, chromosome, bin_loc):
    # Individual comparisons data
    lines = []
    unique_groups = get_unique_matrices(filtered_matrix)
    common_groups = get_common_matrices(filtered_matrix)
    bin_label = make_bin_label(chromosome, bin_loc)

    for matrix in unique_groups:
        cpg_matrix = np.array(matrix.drop(['class', 'input'], axis=1))
        # get a semi-colon separated string of 1s and 0s representing the CpG pattern
        cpg_pattern = ";".join([str(int(x)) for x in list(cpg_matrix[0])])
        m_mean = cpg_matrix.mean()
        num_cpgs = cpg_matrix.shape[1]
        read_number = len(matrix)
        input_label = matrix['input'].unique()[0]
        class_label = matrix['class'].unique()[0]
        out_line = ",".join([bin_label, input_label, str(m_mean), str(class_label), str(read_number),
                             str(num_cpgs), cpg_pattern])
        lines.append(out_line)

    for matrix in common_groups:
        cpg_matrix = np.array(matrix.drop(['class', 'input'], axis=1))
        # get a semi-colon separated string of 1s and 0s representing the CpG pattern
        cpg_pattern = ";".join([str(int(x)) for x in list(cpg_matrix[0])])
        m_mean = cpg_matrix.mean()
        num_cpgs = cpg_matrix.shape[1]
        read_number = len(matrix)
        input_label = 'AB'
        class_label = matrix['class'].unique()[0]
        out_line = ",".join([bin_label, input_label, str(m_mean), str(class_label), str(read_number),
                             str(num_cpgs), cpg_pattern])
        lines.append(out_line)

    return lines


# MAIN METHOD

def process_bins(bin):
    """
    This is the main method and should be called using Pool.map It takes one bin location and uses the other helper
    functions to get the reads, form the matrix, cluster it with DBSCAN, and output the cluster data as text lines
    ready to writing to a file.
    :param bin: string in this format: "chr19_55555"
    :return: a list of lines representing the cluster data from that bin
    """

    bam_parser_A = BamFileReadParser(input_bam_a, 20, read1_5=mbias_read1_5, read1_3=mbias_read1_3,
                                     read2_5=mbias_read2_5, read2_3=mbias_read2_3, no_overlap=no_overlap)
    bam_parser_B = BamFileReadParser(input_bam_b, 20, read1_5=mbias_read1_5, read1_3=mbias_read1_3,
                                     read2_5=mbias_read2_5, read2_3=mbias_read2_3, no_overlap=no_overlap)

    chromosome, bin_loc = bin.split("_")
    bin_loc = int(bin_loc)

    reads_A = bam_parser_A.parse_reads(chromosome, bin_loc - bin_size, bin_loc)
    reads_B = bam_parser_B.parse_reads(chromosome, bin_loc - bin_size, bin_loc)

    # This try/catch block returns None for a bin if any discrepancies in the data format of the bins are detected.
    # The Nones are filtered out during the output of the data
    try:
        matrix_A = bam_parser_A.create_matrix(reads_A)
        matrix_B = bam_parser_B.create_matrix(reads_B)
    except ValueError as e:
        logging.error("ValueError when creating matrix at bin {}. Stack trace will be below if log level=DEBUG".format(bin))
        logging.debug(str(e))
        return None
    except InvalidIndexError as e:
        logging.error("Invalid Index error when creating matrices at bin {}".format(bin))
        logging.debug(str(e))
        return None

    # drop reads without full coverage of CpGs
    matrix_A = matrix_A.dropna()
    matrix_B = matrix_B.dropna()

    # if read depths are still not a minimum, skip
    if matrix_A.shape[0] < read_depth_req or matrix_B.shape[0] < read_depth_req:
        # print("{}: Failed read req with out {} reads in one file".format(bin, str(matrix_B.shape[0])))
        # sys.stdout.flush()
        return None

    # create labels and add to dataframe
    labels_A = ['A'] * len(matrix_A)
    labels_B = ['B'] * len(matrix_B)
    matrix_A['input'] = labels_A
    matrix_B['input'] = labels_B

    try:
        full_matrix = pd.concat([matrix_A, matrix_B])
    except ValueError as e:
        logging.error("Matrix concat error in bin {}".format(bin))
        # logging.debug(str(e))
        return None

    # Get data without labels for clustering
    data_to_cluster = np.matrix(full_matrix)[:, :-1]

    # Create DBSCAN classifier and cluster add cluster classes to df
    clf = DBSCAN(min_samples=2)
    try:
        labels = clf.fit_predict(data_to_cluster)
    except ValueError as e:
        # log error
        logging.error("ValueError when trying to cluster bin {}".format(bin))
        logging.debug(str(e))
        return None

    full_matrix['class'] = labels

    # Filter out any clusters with less than a minimum
    filtered_matrix = filter_data_frame(full_matrix, cluster_min)

    # return generate_output_data(filtered_matrix, chromosome, bin_loc)
    return generate_individual_matrix_data(filtered_matrix, chromosome, bin_loc)


if __name__ == "__main__":

    def str2bool(v):
        if v.lower() == 'true':
            return True
        elif v.lower() == 'false':
            return False
        else:
            raise argparse.ArgumentTypeError("Boolean value expected.")


    # Set command line arguments
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-a", "--input_bam_A",
                            help="First Input bam file, coordinate sorted with index present")
    arg_parser.add_argument("-b", "--input_bam_B",
                            help="Second Input bam file, coordinate sorted with index present")
    arg_parser.add_argument("-o", "--output_dir",
                            help="Output directory to save figures, defaults to bam file loaction")
    arg_parser.add_argument("-bins",
                            help="File with each line being one bin to extract and analyze, "
                                 "generated by CalculateCompleteBins")
    arg_parser.add_argument("-bin_size", help="Size of bins to extract and analyze, default=100", default=100)
    arg_parser.add_argument("-m", "--cluster_member_minimum",
                            help="Minimum number of members a cluster should have for it to be considered, default=4",
                            default=4)
    arg_parser.add_argument("-r", "--read_depth",
                            help="Minium number of reads covering all CpGs that the bins should have to analyze, default=10",
                            default=10)
    arg_parser.add_argument("-n", "--num_processors",
                            help="Number of processors to use for analysis, default=1",
                            default=1)
    arg_parser.add_argument("--read1_5", help="integer, read1 5' m-bias ignore bp, default=0", default=0)
    arg_parser.add_argument("--read1_3", help="integer, read1 3' m-bias ignore bp, default=0", default=0)
    arg_parser.add_argument("--read2_5", help="integer, read2 5' m-bias ignore bp, default=0", default=0)
    arg_parser.add_argument("--read2_3", help="integer, read2 3' m-bias ignore bp, default=0", default=0)
    arg_parser.add_argument("--no_overlap", help="bool, remove any overlap between paired reads and stitch"
                                                 " reads together when possible, default=True",
                            type=str2bool, const=True, default='True', nargs='?')

    args = arg_parser.parse_args()

    # Assign arg parser vars to new variables, not necesary, but I like it
    input_bam_a = args.input_bam_A
    input_bam_b = args.input_bam_B
    bins_file = args.bins
    bin_size = int(args.bin_size)
    cluster_min = int(args.cluster_member_minimum)
    read_depth_req = int(args.read_depth)
    num_processors = int(args.num_processors)
    no_overlap = args.no_overlap
    mbias_read1_5 = int(args.read1_5)
    mbias_read1_3 = int(args.read1_3)
    mbias_read2_5 = int(args.read2_5)
    mbias_read2_3 = int(args.read2_3)


    # todo write input params to log_file for record keeping

    # Check all inputs are supplied
    if not input_bam_a or not input_bam_b or not bins_file:
        print("Please make sure all required input files are supplied")
        logging.error("All required input files were not supplied. Exiting error code 1.")
        sys.exit(1)


    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.dirname(input_bam_a)

    # Create output dir if it doesnt exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Set up logging
    start_time = datetime.datetime.now().strftime("%y-%m-%d")
    log_file = os.path.join(output_dir, "Clustering.{}.{}.log".format(os.path.basename(input_bam_a), start_time))

    # todo adjust this with a -v imput param
    logging.basicConfig(filename=os.path.join(output_dir, log_file), level=logging.DEBUG)

    # Read in bins
    bins=[]
    with open(bins_file, 'r') as f:
        for line in f:
            data = line.strip().split(",")
            # bins.append("_".join([data[0], data[2]]))
            bins.append(data[0])

    pool = Pool(processes=num_processors)
    logging.info("Starting workers pool, using {} processors".format(num_processors))
    logging.info("M bias inputs received, ignoring the following:\nread 1 5': {}bp\n"
                 "read1 3': {}bp\nread2 5: {}bp\nread2 3': {}bp".format(mbias_read1_5, mbias_read1_3, mbias_read2_5, mbias_read2_3))

    # Results is a list of lists
    results = pool.map(process_bins, bins)

    # Convert the results into two output csv files for human analysis
    output = OutputIndividualMatrixData(results)
    output.write_to_output(output_dir, "Clustering.{}.{}".format(os.path.basename(input_bam_a), start_time))

    logging.info("Done")
