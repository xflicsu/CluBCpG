import pysam
import argparse
import pandas as pd
import numpy as np


class BamFileReadParser():

    def __init__(self, bamfile, quality_score):
        self.mapping_quality = quality_score
        self.bamfile = bamfile

        self.OpenBamFile = pysam.AlignmentFile(bamfile, 'rb')

    # Take an AlignmentSegment extract the XM tag, and return the values
    def get_metylation_tags(self, read):
        tags = read.get_tags()
        for tag in tags:
            if tag[0] == 'XM':
                return tag[1]

    # Take a list of tags and positions, return tuples consisting of (position, tag)
    def merge_pos_tags(self, tags, positions, start_pos, stop_pos):
        output = []
        for pos, status in list(zip(positions, tags)):
            if pos >= start_pos and pos <= stop_pos:
                output.append((pos,status))

        return output

    # Take a list of tuples (pos, tag) and reduce it to only CpG sites
    def extract_cpgs(self, pos_tags):
        read_cpgs = []
        for item in pos_tags:
            if item[1] is 'Z' or item[1] is 'z':
                read_cpgs.append(item)

        return read_cpgs

    def parse_reads(self, chromosome, start_pos, stop_pos):
        reads = []
        for read in self.OpenBamFile.fetch(chromosome, start_pos, stop_pos, multiple_iterators=True):
            if read.mapping_quality < self.mapping_quality:
                continue
            reads.append(read)

        reads_cpgs = []
        for read in reads:
            tags = self.get_metylation_tags(read)
            pos = read.get_reference_positions()
            if read.flag == 99 or read.flag == 147:
                pos = list(np.array(pos) + 1)
            pos_tags = self.merge_pos_tags(tags, pos, start_pos, stop_pos)
            cpgs = self.extract_cpgs(pos_tags)
            reads_cpgs.append(cpgs)

        return reads_cpgs


    def create_matrix(self, read_cpgs):
        series = []
        for data in read_cpgs:
            positions = []
            statues = []
            for pos, status in data:
                positions.append(pos)
                statues.append(status)
            series.append(pd.Series(statues, positions))

        matrix = pd.concat(series, axis=1)
        matrix = matrix.replace('Z', 1)
        matrix = matrix.replace('z', 0)

        return matrix.T


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("input_bam", help="bam file")
    parser.add_argument("chromosome", help="chromosome to extract from, example: chr19")
    parser.add_argument("end_coordinate", help="Specifcy the final coordinate of the region you wish to extract, example"
                                               " 500 would give you a region randing from bp window_size-500")
    parser.add_argument("-w", "--window", help="Size of the region in bp you with you convert into a matrix",
                        default=200)
    parser.add_argument("-q", "--quality", help="Minimum mapping quality for read to be considered default=20",
                        default=20)

    args = parser.parse_args()

    bam_file = args.input_bam
    quality_score = args.quality
    window_size = args.window
    stop_pos = int(args.end_coordinate)
    chromosome = args.chromosome

    bamfileparser = BamFileReadParser(bam_file, quality_score)

    data = bamfileparser.parse_reads(chromosome, stop_pos-window_size, stop_pos)

    matrix = bamfileparser.create_matrix(data)

    print(matrix)
