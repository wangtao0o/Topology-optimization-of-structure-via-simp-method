from numpy import *
import numpy as np
import global_variable
from finite_element_analysis import *
from postprocessor import *
from traits.api import HasTraits, Instance, Property, Enum,Range,on_trait_change,Int
import  time

from mayavi import mlab
class Simp(HasTraits):
    """
    函数中各个parameter:

    Parameters
    ----------
    需要从ANSYS获得以及需要用户输入的数据：
    U:  NxL列向量，节点解，N为节点数,L为坐标轴数，2D对应x,y.3D对应x,y,z
    stress:Nx2数组，第一列节点编号，第二列修匀后的节点应力
    strain:Nx2数组，第一类节点编号，第二列修匀后的节点应变
    K: ExRxL数组,单元刚度矩阵汇总，E为单元数,R、L为单元刚度矩阵的行和列
    ELEMENT_ATTRIBUTES:  ExN数组，单元信息，E是单元数，N为单元节点编号
    CENTERS: Ex3数组，单元中心坐标, E单元数目，每行3列分别为中心x、y、z坐标
    V:1xE数组，单元体积，E单元数目
    penal: 标量，simp法的密度惩罚因子
    volfrac:  标量，体积减少百分比
    rmin: 标量，SIMP法棋盘格现象抑制范围，与结构最小杆件的尺寸将与rmin接近

    SIMP法需要的arguments：ue，k0，center,v,penal,volfrac,rmin,xe
    Ue:各个单元的节点解
    Ke:各个单元刚度矩阵
    center:各个单元的中心坐标
    Ve:各个单元的体积
    penal: 标量，simp法的密度惩罚因子
    volfrac:  标量，体积减少百分比
    rmin:标量，SIMP法棋盘格现象抑制范围，与结构最小杆件的尺寸将与rmin接近
    x:  1xE数组，各个单元的相对密度，也是simp法求解的目标
    """

    loop = Int(0)#以loop作为图形更新的监听对象
    def __init__(self):
        #初始化所需要的数据
        self.resultdata = ResultData()
        self.ansys_solver = FiniteElementAnalysis()
        self.strain_energy = []
        self.finished = False
    def get_distance_table(self):
        """
        生成单元中心之间的距离表格distance

        Returns
        ----------
        distance:单元中心之间的距离

        Examples
        ----------
        distance[3][4]:表示3号与4号单元之间的距离

        """
        # for loop edition
        # length = global_variable.CENTERS.shape[0]
        # distance = zeros(shape = (length, length))
        # start = time.clock()
        # for i in range(length):
        #     for j in range(i+1,length):
        #         distance[i,j] = np.linalg.norm(global_variable.CENTERS[i,1:]-global_variable.CENTERS[j,1:])
        # distance+=distance.T
        # end = time.clock()
        # print(end-start)
        # return distance

        #vectorize edition
        length = global_variable.CENTERS.shape[0]
        distance = zeros(shape=(length, length))
        start = time.clock()
        distance = (global_variable.CENTERS[:,1].reshape(-1,1)-global_variable.CENTERS[:,1].reshape(-1,1).T)**2
        distance = distance + (global_variable.CENTERS[:,2].reshape(-1,1)-global_variable.CENTERS[:,2].reshape(-1,1).T)**2
        distance = distance + (global_variable.CENTERS[:,3].reshape(-1,1)-global_variable.CENTERS[:,3].reshape(-1,1).T)**2
        distance = np.sqrt(distance)
        end = time.clock()
        print(end-start)
        return distance

    def de_checkboard(self,rmin, x, dc):
        """
        更新每个单元应变能对与密度的敏度,消除棋盘格现象与网格不独立现象的敏度过滤算法

        Parameters
        ----------
        rmin:最小过滤半径
        x:单元密度
        dc:没有过滤的敏度

        Returns
        ----------
        corrected_dc:过滤之后的敏度
        """

        a = array(dc,dtype = float)
        corrected_dc = []
        i = 0
        for _ in dc:
            corrected_dc_demonimator = 0.0
            corrected_dc_numerator = 0.0
            #寻找对当前单元满足条件 rmin-distance>0的elements
            satisfied_elements,delta = self.find_satisfied_elements(i,rmin)
            j=0
            for element in satisfied_elements[0]:
                Hf =global_variable.V[element,1]*delta[j]
                corrected_dc_demonimator = corrected_dc_demonimator+Hf
                corrected_dc_numerator = corrected_dc_numerator + Hf * x[element] * dc[element]
                j=j+1
            corrected_dc.append(corrected_dc_numerator/(x[i]*corrected_dc_demonimator))
            i = i+1
        return corrected_dc


    def find_satisfied_elements(self,i,rmin):
        """
        寻找当前单元i周围中心距离在rmin以内的单元

        Returns
        ----------
        satisfied_elements:在过滤半径之内的单元
        delta:距离差
        """
        result = rmin -self.distance[i]
        satisfied_elements = np.argwhere(result>0).T
        delta = result[satisfied_elements[0].tolist()]
        return satisfied_elements,delta


    def oc(self, x, volfrac, corrected_dc):
        """
        优化准则法
        """
        lambda1 = 0; lambda2 = 100000; move = 0.2
        while(lambda2-lambda1>1e-4):
            lambda_mid = 0.5*(lambda2+lambda1)
            B = x*sqrt((array(corrected_dc,dtype = float))/(lambda_mid * global_variable.V[:,1]))
            xnew = maximum(0.001, maximum(x-move, minimum(1.0, minimum(x + move,B))))#由里到外，先比上界，再比下界
            if sum(xnew*global_variable.V[:,1])-volfrac*sum(global_variable.V[:,1])>0:
                lambda1 = lambda_mid
            else:
                lambda2 = lambda_mid
        return xnew

    #for loop editon
    # def simp(self,penal = 3, volfrac = 0.4, rmin = 4e-4):
    #     """
    #     SIMP优化算法
    #     """
    #     #初始化数据
    #     self.distance = self.get_distance_table()
    #     x = volfrac*np.ones(global_variable.ELEMENT_COUNTS)
    #     change = 1;
    #     #开始迭代
    #     while change > 0.05:
    #         c = 0
    #         xold = x;
    #         U, stress, strain = self.ansys_solver.get_result_data(x,penal)
    #         #目标函数与敏度分析
    #         #总应变能
    #         i = 0
    #         dc = []
    #         for xe in  x:
    #             nodes_number = global_variable.ELEMENT_ATTRIBUTES[i]
    #             Ue = []
    #             for node_number in nodes_number:
    #                 Ue.append(U[node_number-1][0])
    #                 Ue.append(U[node_number-1][1])
    #             Ue = array(Ue)
    #             c = c + (xe**penal)*matrix(Ue)*matrix(global_variable.K[i])*matrix(Ue).T
    #             dc.append((penal*(xe**(penal-1))*(matrix(Ue)*matrix(global_variable.K[i])*matrix(Ue).T))[0,0])
    #             i = i+1
    #         #更新每个单元应变能对与密度的敏度：消除棋盘格现象的敏度过滤算法
    #         corrected_dc = self.de_checkboard( rmin, x, dc)
    #         #OC优化准则发对密度进行更新
    #         x = self.oc(x, volfrac, corrected_dc)
    #         change = max(abs(x-xold))
    #         self.strain_energy.append(c[0,0])
    #         print("change:",change,"    c：",c[0,0],"    loop:",self.loop)
    #         #更新每一次迭代的结果，整个内存只保存了当前迭代结果
    #         self.resultdata.undate_ansys_date(U, stress, strain, x)
    #         #将每一步的迭代结果写入本地内存，以为后续生成动画
    #         self.resultdata.write_unstructured_data(loop=self.loop)
    #         self.loop = self.loop + 1
    #
    #         # if self.loop>20:
    #         #     break
    #     self.finished = True
    #     return x
    #vectorizing edion
    def simp(self,penal = 3, volfrac = 0.4, rmin = 1.2):
        """
        SIMP优化算法
        """
        #初始化数据
        self.distance = self.get_distance_table()
        x = volfrac*np.ones(global_variable.ELEMENT_COUNTS)
        change_c = change_x = 1;
        c = 0
        #开始迭代
        while change_c > 0.001 or change_x >0.005:
            c_old =c
            xold = x;
            U, stress, strain = self.ansys_solver.get_result_data(x,penal)
            #目标函数与敏度分析
            #总应变能
            Ue=np.zeros((global_variable.ELEMENT_COUNTS,global_variable.DIM,1))

            for i in range(global_variable.ELEMENT_COUNTS):
                nodes_number = global_variable.ELEMENT_ATTRIBUTES[i]
                Ue[i,:,:] =U[[nodes_number - 1],:].reshape(-1,global_variable.DIM,1)

            c = matmul((x ** penal).reshape(global_variable.ELEMENT_COUNTS,1,1) , matmul(matmul(Ue.transpose((0,2,1)),global_variable.K),Ue))
            c = sum(c,axis = 0)[0][0]
            dc = matmul((penal*(x ** (penal-1))).reshape(global_variable.ELEMENT_COUNTS, 1, 1), matmul(matmul(Ue.transpose((0, 2, 1)), global_variable.K), Ue))
            dc = dc[:,0,0].tolist()
            #更新每个单元应变能对与密度的敏度：消除棋盘格现象的敏度过滤算法
            corrected_dc = self.de_checkboard( rmin, x, dc)
            #OC优化准则发对密度进行更新
            x = self.oc(x, volfrac, corrected_dc)
            change_x = max(abs(x-xold))
            change_c = abs(c_old - c)
            self.strain_energy.append(c)
            print("change_c:",change_c,"    change_x:",change_x,"    c：",c,"    loop:",self.loop)
            #更新每一次迭代的结果，整个内存只保存了当前迭代结果
            self.resultdata.undate_ansys_date(U, stress, strain, x)
            #将每一步的迭代结果写入本地内存，以为后续生成动画
            self.resultdata.write_unstructured_data(loop=self.loop)
            self.loop = self.loop + 1

            # if self.loop>20:
            #     break
        self.finished = True
        return x

#单元测试
if __name__=='__main__':
    global_variable.initialize_global_variable(DIM = 8)
    simp_solver = Simp(dim = 8)
    density = simp_solver.simp()

    # x = simp_solver.x_axis
    y = simp_solver.strain_energy
    # z = simp_solver.z_axis
    l = mlab.plot3d(x, y, z, representation='surface')
    # l = mlab.plot3d()
    mlab.show()







