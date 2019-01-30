from CpGNet import CpGNet
import numpy as np
from keras.models import load_model
import keras.backend as K
import os
import warnings

class ImputeWithCpGNet:

    def __init__(self, cpg_density: int, bin: str, bin_size=100, path_to_models=None):
        """Class used to connect this package with CpGNet's imputation classes
        
        Arguments:
            cpg_density {int} -- number of CpGs in bin
            bin {str} -- bin in format "chr1_4444"
        
        Keyword Arguments:
            bin_size {int} -- size of bin in base-pairs (default: {100})
            path_to_models {[str]} -- Path to directory containing models built by TrainModels scripy (default: {None})
        
        Raises:
            AttributeError -- Raised if a path to the models directory is not specified or does not exist
        """

        warnings.warn("Stop using this class, it is being deprecated", DeprecationWarning)
        self.cpg_density = cpg_density
        self.bin = bin
        self.bin_size = bin_size
        if not path_to_models or not os.path.exists(path_to_models):
            raise AttributeError("Path to models is not specified or does not exist")
        self.path_to_models = path_to_models
        self.model = self.get_model()
    

    def get_model(self):
        """Called during init to load model from disk into instance object
        
        Returns:
            [type] -- CpGNet model
        """

        net = CpGNet(cpgDensity=self.cpg_density)
        net.model = load_model(os.path.join(self.path_to_models, "saved_model_{}_cpgs.h5".format(self.cpg_density)))
        return net

    # Take the predicted matrix, convert to 1 and 0 when confident, otherwise nan
    def postprocess(self, predicted_matrix):
        """Takes array with predicted values and rounds them to 0 or 1 if threshold is exceeded
        
        Arguments:
            predicted_matrix {[type]} -- matrix generated by imputation
        
        Returns:
            [type] -- predicted matrix predictions as 1, 0, or NaN
        """

        processed_array = []
        for array in predicted_matrix:
            new_array = []
            for item in array:
                if item != 1 and item != 0:
                    if item <= 0.2: #TODO un-hardcode this
                        new_array.append(0.0)
                    elif item >= 0.8: #TODO un-hardcode this
                        new_array.append(1.0)
                    else:
                        new_array.append(np.nan)
                else:
                    new_array.append(item)

            processed_array.append(new_array)

        return np.array(processed_array)

    def impute_matrix(self, matrix, postprocess=True):
        """
        :param matrix: 2D np array with unknowns as -1
        :param positions: 1D np array of chromosomal positions (ints)
        :param postprocess: Imply classes from imputation, if False, returns probabilities instead of predictions
        :return: A matrix imputed with highly confident predictions, less confident regions are assigned np.nan
        """

        predicted_matrix = self.model.impute(matrix)
        if postprocess:
            predicted_matrix = self.postprocess(predicted_matrix)

        # This call forces tensorflow to release memory, otherwise a large memory leak happens when executing in parallel
        K.clear_session()
        return predicted_matrix


class TrainWithCpGNet:

    def __init__(self, cpg_density=None, save_path=None):
        """
        Class to train a CpGNet model from input data
        :param cpg_density: Number of CpGs
        :param save_path: Location of folder to save the resulting model files. One per cpg density
        """
        if not cpg_density:
            raise AttributeError("CpG density must be specified")
        if not save_path:
            raise AttributeError("Folder to save trained model must be specified")
        self.save_path = save_path
        self.cpg_density = cpg_density
        self.net = CpGNet(cpgDensity=cpg_density)

    def save_net(self, model):
        """
        Save the network to a file
        :param model: The trained CpGNet model. Located at CpGNet.model
        :return: Path to the saved model
        """
        file_name = "saved_model_{}_cpgs.h5".format(self.cpg_density)
        output = os.path.join(self.save_path, file_name)
        model.save(output)
        print("Saved {} cpg model to {}".format(self.cpg_density, output))

        return output


    def train_model(self, bins: iter):
        """
        Train the CpGNet model on a list of provided bins
        :param bins: iterable containing CpG matrices of 1 (methylated), 0 (unmethylated), and -1 (unknown)
        :return: Path to the saved model file
        """
        self.net.train(bins)
        output = self.save_net(self.net.model)

        return output
